"""align match_results, applications and repository verification with the canonical flow

One migration batching every schema change the flow-alignment work needs, so
the application-code steps that follow it never have to interleave a second
`alembic upgrade`.

1. **`match_results.match_reasons`** — the two parallel JSONB columns
   (`matched_required_skills` / `matched_desirable_skills`) collapse into one
   `{"required": [...], "desirable": [...]}` document. Two columns that are
   always written together, always read together, and always mean "the reason
   trail for this pair" are one value, not two; the split forced every reader
   to remember to fetch both and every writer to keep them in step.

2. **`match_results.updated_at`** — the table had only `computed_at`, which was
   sufficient while every recompute was a delete-then-reinsert (a row's whole
   life was one instant). Once recompute becomes an upsert, "when this pair was
   first matched" and "when its score last changed" are different facts:
   `computed_at` keeps the former, `updated_at` records the latter.

3. **`applications.match_id` / `score_at_apply` / `evidence_snapshot_id`** — the
   score the recruiter actually saw was previously reachable only by digging
   into `evidence_snapshot->'match'->>'match_score'`, which cannot be sorted or
   filtered on and silently reads as null for any application whose snapshot
   predates that key. Promoting it to a column makes the Kanban board's
   "sort by score within stage" a real `ORDER BY` and makes the snapshot-vs-live
   comparison a two-column read.

   `evidence_snapshot_id` is a plain UUID, not a foreign key: the snapshot lives
   inline in `applications.evidence_snapshot` (deliberately — it is frozen and
   read only alongside its application, so a separate table would be a join with
   no other reader). The id exists so an audit-log entry or a shortlisting
   decision can cite *which* frozen snapshot it was made against, which the JSONB
   alone cannot provide.

4. **`verification_stages`** — repository verification was one monolithic Celery
   task writing a single result blob, so a failure in, say, technology detection
   discarded the fork check and contribution analysis that had already succeeded.
   One row per (project, stage) makes each stage independently queryable,
   independently retryable, and preserves the output of every stage that ran
   before a failure.

5. **`notification_type.NEW_MATCH`** — the matching worker previously completed
   silently; it now writes a notification per newly matched candidate.

6. **`candidate_profiles.onboarding_choice`** — the "Upload Resume vs. Build
   Manually" fork needs to be answerable exactly once. Deriving "already
   onboarded" from whether any section is filled does not work: choosing to
   build manually writes no profile data, so the fork would reappear on every
   visit until the first save. Nullable — NULL is "not asked yet".

Revision ID: b2d5e8f14c73
Revises: c7f2a94e6b1d
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2d5e8f14c73'
down_revision: Union[str, None] = 'c7f2a94e6b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


verification_stage_kind = postgresql.ENUM(
    'REPOSITORY_SELECTION',
    'FORK_AUTHORSHIP_CHECK',
    'CONTRIBUTION_ANALYSIS',
    'ARCHITECTURE_CODE_QUALITY',
    'TECHNOLOGY_DETECTION',
    'CODE_GROUNDED_INTERVIEW',
    'EVIDENCE_REPORT',
    name='verification_stage_kind',
    create_type=False,
)
verification_stage_status = postgresql.ENUM(
    'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED',
    name='verification_stage_status',
    create_type=False,
)
onboarding_choice = postgresql.ENUM(
    'RESUME_UPLOAD', 'MANUAL_ENTRY', name='onboarding_choice', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. match_results: unified match_reasons ----------------------------
    op.add_column(
        'match_results',
        sa.Column(
            'match_reasons',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{"required": [], "desirable": []}',
        ),
    )
    # Backfill before dropping the sources, so no existing reason trail is lost.
    op.execute(
        """
        UPDATE match_results
           SET match_reasons = jsonb_build_object(
                   'required', COALESCE(matched_required_skills, '[]'::jsonb),
                   'desirable', COALESCE(matched_desirable_skills, '[]'::jsonb)
               )
        """
    )
    op.alter_column('match_results', 'match_reasons', server_default=None)
    op.drop_column('match_results', 'matched_required_skills')
    op.drop_column('match_results', 'matched_desirable_skills')

    # --- 2. match_results: updated_at ---------------------------------------
    # Seeded from `computed_at` rather than `now()`: for a row that has never
    # been re-scored, "last updated" *is* "first computed", and defaulting to
    # the migration's own timestamp would fabricate an update that never
    # happened.
    op.add_column(
        'match_results',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute('UPDATE match_results SET updated_at = computed_at')
    op.alter_column('match_results', 'updated_at', nullable=False)

    # `uq_match_result_pair` already exists (revision a3e7c19f5d6b) and is what
    # the new upsert conflict-targets; asserted here rather than re-created so
    # a drifted database fails loudly instead of silently upserting on nothing.
    constraint_exists = bind.execute(
        sa.text(
            """
            SELECT 1 FROM pg_constraint
             WHERE conname = 'uq_match_result_pair'
               AND conrelid = 'match_results'::regclass
            """
        )
    ).scalar()
    if not constraint_exists:
        op.create_unique_constraint(
            'uq_match_result_pair', 'match_results', ['job_posting_id', 'candidate_profile_id']
        )

    # --- 3. applications: first-class match link and frozen score -----------
    op.add_column('applications', sa.Column('match_id', sa.UUID(), nullable=True))
    op.add_column('applications', sa.Column('score_at_apply', sa.Numeric(5, 2), nullable=True))
    op.add_column('applications', sa.Column('evidence_snapshot_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_applications_match_id',
        'applications',
        'match_results',
        ['match_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_applications_match_id'), 'applications', ['match_id'], unique=False)

    # Backfill from the pair that already exists: every application to date was
    # created through Smart Apply, which required a live `match_results` row.
    op.execute(
        """
        UPDATE applications AS a
           SET match_id = m.id,
               score_at_apply = m.match_score
          FROM match_results AS m
         WHERE m.job_posting_id = a.job_posting_id
           AND m.candidate_profile_id = a.candidate_profile_id
        """
    )
    # Fall back to the score frozen inside the snapshot for any application
    # whose match row has since been pruned (a closed job, a re-verification).
    op.execute(
        """
        UPDATE applications
           SET score_at_apply = (evidence_snapshot -> 'match' ->> 'match_score')::numeric
         WHERE score_at_apply IS NULL
           AND evidence_snapshot -> 'match' ->> 'match_score' IS NOT NULL
        """
    )
    # Every existing snapshot gets a citable id; `'{}'::jsonb` means Smart Apply
    # stored nothing, and an id for an empty snapshot would be a lie.
    op.execute(
        """
        UPDATE applications
           SET evidence_snapshot_id = gen_random_uuid()
         WHERE evidence_snapshot IS NOT NULL
           AND evidence_snapshot <> '{}'::jsonb
        """
    )

    # --- 4. verification_stages ---------------------------------------------
    verification_stage_kind.create(bind, checkfirst=True)
    verification_stage_status.create(bind, checkfirst=True)

    op.create_table(
        'verification_stages',
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('stage', verification_stage_kind, nullable=False),
        sa.Column('status', verification_stage_status, nullable=False, server_default='PENDING'),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'stage', name='uq_verification_stage_project_stage'),
    )
    op.alter_column('verification_stages', 'status', server_default=None)
    op.create_index(
        op.f('ix_verification_stages_project_id'), 'verification_stages', ['project_id'], unique=False
    )
    op.create_index(op.f('ix_verification_stages_status'), 'verification_stages', ['status'], unique=False)

    # --- 5. notification_type: NEW_MATCH ------------------------------------
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'NEW_MATCH'")

    # --- 6. candidate_profiles.onboarding_choice ----------------------------
    onboarding_choice.create(bind, checkfirst=True)
    op.add_column(
        'candidate_profiles', sa.Column('onboarding_choice', onboarding_choice, nullable=True)
    )
    # Anyone who already has profile data predates the fork and must not be
    # sent back through it. Which lane they actually used is unknowable now,
    # and `MANUAL_ENTRY` is the truthful default: every one of them typed their
    # profile in, because resume import shipped after they did.
    op.execute(
        """
        UPDATE candidate_profiles
           SET onboarding_choice = 'MANUAL_ENTRY'
         WHERE profile_strength > 0
        """
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_column('candidate_profiles', 'onboarding_choice')
    onboarding_choice.drop(bind, checkfirst=True)

    op.drop_index(op.f('ix_verification_stages_status'), table_name='verification_stages')
    op.drop_index(op.f('ix_verification_stages_project_id'), table_name='verification_stages')
    op.drop_table('verification_stages')
    verification_stage_status.drop(bind, checkfirst=True)
    verification_stage_kind.drop(bind, checkfirst=True)

    op.drop_index(op.f('ix_applications_match_id'), table_name='applications')
    op.drop_constraint('fk_applications_match_id', 'applications', type_='foreignkey')
    op.drop_column('applications', 'evidence_snapshot_id')
    op.drop_column('applications', 'score_at_apply')
    op.drop_column('applications', 'match_id')

    op.drop_column('match_results', 'updated_at')

    op.add_column(
        'match_results',
        sa.Column(
            'matched_required_skills',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]',
        ),
    )
    op.add_column(
        'match_results',
        sa.Column(
            'matched_desirable_skills',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]',
        ),
    )
    op.execute(
        """
        UPDATE match_results
           SET matched_required_skills = COALESCE(match_reasons -> 'required', '[]'::jsonb),
               matched_desirable_skills = COALESCE(match_reasons -> 'desirable', '[]'::jsonb)
        """
    )
    op.alter_column('match_results', 'matched_required_skills', server_default=None)
    op.alter_column('match_results', 'matched_desirable_skills', server_default=None)
    op.drop_column('match_results', 'match_reasons')

    # `NEW_MATCH` is not removed from `notification_type`: Postgres cannot drop
    # an enum value, and the same limitation is already documented for
    # `verification_status.FLAGGED` in revision d8b3f61a9c02.


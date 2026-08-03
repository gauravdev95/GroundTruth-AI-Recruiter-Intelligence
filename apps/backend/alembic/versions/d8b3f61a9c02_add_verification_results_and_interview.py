"""add verification result columns, github oauth storage, and the AI interview tables

Three things, none of which touches an already-applied migration:

1. **Verification results.** Every claim table (`github_accounts`,
   `coding_platform_accounts`, `projects`, `certificates`) gets
   `verification_score` / `verification_source` / `verification_payload` so
   `src/jobs/tasks/verification.py` has somewhere to write the outcome of a
   check, plus the audit payload the check was based on. `experiences` gets
   the full verification quadruple (`verification_status`, `verified_at`,
   `verification_score`, `verification_source`, `verification_payload`) —
   unlike the other four claim tables, `experiences` was never wired to
   verification at all in the profile builder, and this migration is what
   turns that on.

   `verification_status` gains a fifth value, `FLAGGED`, for a claim that is
   visible but could not be strongly confirmed (an unmatched certificate
   issuer domain, a coding-platform handle checked only by a reachability
   heuristic, a self-reported experience with no independent source of
   truth). `ALTER TYPE ... ADD VALUE` is not used anywhere in this migration
   (no INSERT/UPDATE references it), which is what keeps it legal inside
   Alembic's single migration transaction — Postgres forbids using a new enum
   label in the same transaction that added it, but does not forbid adding it.

2. **GitHub OAuth storage.** `github_accounts` gains the token-storage columns
   `docs/DATA_MODEL.md` §3 already specified for this table
   (`access_token_encrypted`, `scopes` — named `token_scopes` here to avoid
   colliding with the ORM's own attribute-naming conventions elsewhere) plus
   `oauth_connected_at`. `github_user_id` and its unique constraint already
   exist from `c3f1a9d47b02`; OAuth is what actually populates it now.

3. **AI interview tables** (`interviews`, `interview_questions`,
   `interview_answers`, `interview_scores`) — new, not previously designed in
   `docs/DATA_MODEL.md` §4 (which scopes interviews to `applications`, which
   don't exist yet). This is a deliberately smaller shape: one interview per
   `(candidate_profile_id, project_id)`, grounded in that project's stored
   verification payload rather than a job application.

Hand-written, same reason as `c3f1a9d47b02`: enums are created once, and
every column/table referencing one passes `create_type=False`.

Revision ID: d8b3f61a9c02
Revises: f7a41c9d3e58
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd8b3f61a9c02'
down_revision: Union[str, None] = 'f7a41c9d3e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


interview_status = postgresql.ENUM(
    'PENDING', 'IN_PROGRESS', 'EVALUATING', 'COMPLETED', 'FAILED',
    name='interview_status',
    create_type=False,
)

_VERIFICATION_RESULT_COLUMNS = (
    'verification_score',
    'verification_source',
    'verification_payload',
)

_CLAIM_TABLES = ('github_accounts', 'coding_platform_accounts', 'projects', 'certificates')


def _add_verification_result_columns(table: str) -> None:
    op.add_column(table, sa.Column('verification_score', sa.Numeric(5, 2), nullable=True))
    op.add_column(table, sa.Column('verification_source', sa.String(length=100), nullable=True))
    op.add_column(
        table,
        sa.Column('verification_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. verification_status: add FLAGGED -------------------------------
    op.execute("ALTER TYPE verification_status ADD VALUE IF NOT EXISTS 'FLAGGED'")

    # --- verification result columns on the four existing claim tables -----
    for table in _CLAIM_TABLES:
        _add_verification_result_columns(table)

    # --- experiences: was never wired to verification at all ---------------
    verification_status_ref = postgresql.ENUM(name='verification_status', create_type=False)
    op.add_column(
        'experiences',
        sa.Column(
            'verification_status',
            verification_status_ref,
            nullable=False,
            server_default='UNVERIFIED',
        ),
    )
    op.alter_column('experiences', 'verification_status', server_default=None)
    op.add_column('experiences', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    _add_verification_result_columns('experiences')

    # --- 2. GitHub OAuth token storage on github_accounts -------------------
    op.add_column('github_accounts', sa.Column('access_token_encrypted', sa.Text(), nullable=True))
    op.add_column(
        'github_accounts',
        sa.Column('token_scopes', sa.String(length=500), nullable=False, server_default=''),
    )
    op.alter_column('github_accounts', 'token_scopes', server_default=None)
    op.add_column(
        'github_accounts', sa.Column('oauth_connected_at', sa.DateTime(timezone=True), nullable=True)
    )

    # --- 3. AI interview tables ---------------------------------------------
    interview_status.create(bind, checkfirst=True)

    op.create_table(
        'interviews',
        sa.Column('candidate_profile_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('status', interview_status, nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('evidence_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('interviews', 'question_count', server_default=None)
    op.create_index(
        op.f('ix_interviews_candidate_profile_id'), 'interviews', ['candidate_profile_id'], unique=False
    )
    op.create_index(op.f('ix_interviews_project_id'), 'interviews', ['project_id'], unique=False)
    op.create_index(op.f('ix_interviews_status'), 'interviews', ['status'], unique=False)

    op.create_table(
        'interview_questions',
        sa.Column('interview_id', sa.UUID(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('grounded_in', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('presented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_id', 'sequence', name='uq_interview_question_sequence'),
    )
    op.alter_column('interview_questions', 'time_limit_seconds', server_default=None)
    op.create_index(
        op.f('ix_interview_questions_interview_id'), 'interview_questions', ['interview_id'], unique=False
    )

    op.create_table(
        'interview_answers',
        sa.Column('interview_question_id', sa.UUID(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('time_taken_seconds', sa.Integer(), nullable=True),
        sa.Column('exceeded_time_limit', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['interview_question_id'], ['interview_questions.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_question_id'),
    )
    op.alter_column('interview_answers', 'exceeded_time_limit', server_default=None)

    op.create_table(
        'interview_scores',
        sa.Column('interview_answer_id', sa.UUID(), nullable=False),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False),
        sa.Column('score', sa.Numeric(5, 2), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['interview_answer_id'], ['interview_answers.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_interview_scores_interview_answer_id'),
        'interview_scores',
        ['interview_answer_id'],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f('ix_interview_scores_interview_answer_id'), table_name='interview_scores')
    op.drop_table('interview_scores')
    op.drop_table('interview_answers')
    op.drop_index(op.f('ix_interview_questions_interview_id'), table_name='interview_questions')
    op.drop_table('interview_questions')
    op.drop_index(op.f('ix_interviews_status'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_project_id'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_candidate_profile_id'), table_name='interviews')
    op.drop_table('interviews')
    interview_status.drop(bind, checkfirst=True)

    op.drop_column('github_accounts', 'oauth_connected_at')
    op.drop_column('github_accounts', 'token_scopes')
    op.drop_column('github_accounts', 'access_token_encrypted')

    for column in ('verification_payload', 'verification_source', 'verification_score'):
        op.drop_column('experiences', column)
    op.drop_column('experiences', 'verified_at')
    op.drop_column('experiences', 'verification_status')

    for table in _CLAIM_TABLES:
        for column in ('verification_payload', 'verification_source', 'verification_score'):
            op.drop_column(table, column)

    # `FLAGGED` is not removed from `verification_status`: Postgres cannot drop
    # a single enum label (only the whole type), and the four claim tables plus
    # `experiences` still reference the type. Downgrading past this migration
    # leaves the label in place, which is harmless — nothing above this
    # revision writes it.

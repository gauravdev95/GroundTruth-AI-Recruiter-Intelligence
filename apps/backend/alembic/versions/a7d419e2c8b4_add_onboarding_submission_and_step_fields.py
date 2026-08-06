"""add onboarding submission, richer project/certificate fields, and three coding platforms

Backs the seven-step onboarding flow. Five additive groups, no rewrites:

1. **`candidate_profiles.onboarding_submitted_at`** — the new dashboard gate.
   Until this revision the gate was *derived* (`meets_section_requirements`:
   sections 1 and 2 complete), which meant it could re-open or re-close under a
   student who did nothing, because a verification worker writing a result
   moves the underlying rows. Onboarding now ends with an explicit act, and
   this column records it.

   **The backfill is the load-bearing part.** Every profile that already
   satisfies the old gate is stamped as submitted, so students who reached the
   dashboard before this deploy keep it. Without it, the first request after
   deploy would bounce every existing student back into onboarding — a
   regression dressed as a feature. `created_at` is used rather than `now()`
   so the timestamp does not falsely claim they submitted at deploy time.

2. **`coding_platform` gains `ATCODER`, `GEEKSFORGEEKS`, `OTHER`.** None has a
   usable public API, so all three are checked by URL reachability and cap at
   `FLAGGED`, like HackerRank and CodeChef before them
   (`jobs/tasks/verification.py`). `OTHER` additionally has no URL template,
   which is what `coding_platform_accounts.custom_platform_name` and a
   client-supplied `profile_url` are for.

3. **`projects` gains `live_demo_url`, `claimed_technologies`, `is_primary`.**
   `claimed_technologies` is a separate column from `technologies` on purpose:
   that one is written by the verification worker from dependency manifests,
   and merging a self-reported list into it would make a claim indistinguishable
   from a detection on the recruiter-facing evidence card.

4. **`certificates` gains the four file columns.** An uploaded certificate is
   stored in the same private bucket resumes use; only the object key is
   persisted, never a URL.

5. **`is_primary` is not backfilled.** No existing project was nominated by
   anybody, and picking one on the student's behalf would invent a claim.

`ALTER TYPE ... ADD VALUE` is legal inside Alembic's single transaction here
for the same reason it was in `e4c92a17f8d3`: Postgres forbids *using* a new
label in the transaction that added it, not adding it, and nothing below
inserts or updates a row carrying one.

Enum labels are the Python member **names** (`GEEKSFORGEEKS`), not the values —
`SAEnum(..., native_enum=True)` stores names, as every prior migration does.

Revision ID: a7d419e2c8b4
Revises: f1a83b6c25d9
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d419e2c8b4'
down_revision: Union[str, None] = 'f1a83b6c25d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Mirrors `completeness._BASIC_FIELDS`. Duplicated in SQL rather than imported
#: because a migration must keep describing the schema as it was at this
#: revision — importing application code would let a later edit to that tuple
#: silently change what this already-applied migration meant.
_BASIC_COMPLETE = """
    p.headline IS NOT NULL AND btrim(p.headline) <> ''
    AND p.college IS NOT NULL AND btrim(p.college) <> ''
    AND p.degree IS NOT NULL
    AND p.branch IS NOT NULL
    AND p.graduation_year IS NOT NULL
    AND p.location IS NOT NULL AND btrim(p.location) <> ''
    AND p.target_role IS NOT NULL
"""


def upgrade() -> None:
    # --- 1. The new onboarding gate ----------------------------------------
    op.add_column(
        'candidate_profiles',
        sa.Column('onboarding_submitted_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Send-once marker for the "verification finished" email.
    op.add_column(
        'candidate_profiles',
        sa.Column('verification_summary_sent_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill: anyone who already passed the old gate stays past it.
    #
    # `verification_summary_sent_at` is stamped in the same statement, which is
    # not cosmetic: these profiles may have claims still sitting `PENDING` from
    # before this deploy, and the first of those to settle would otherwise mail
    # every one of them a summary of checks they never asked for. Suppressing
    # it makes the email a feature of the new flow rather than a deploy event.
    op.execute(
        f"""
        UPDATE candidate_profiles AS p
           SET onboarding_submitted_at = p.created_at,
               verification_summary_sent_at = p.created_at
         WHERE p.onboarding_submitted_at IS NULL
           AND ({_BASIC_COMPLETE})
           AND EXISTS (
                 SELECT 1 FROM github_accounts g
                  WHERE g.candidate_profile_id = p.id AND g.deleted_at IS NULL
               )
           AND EXISTS (
                 SELECT 1 FROM coding_platform_accounts c
                  WHERE c.candidate_profile_id = p.id AND c.deleted_at IS NULL
               )
        """
    )

    # --- 2. coding_platform: three more platforms --------------------------
    for label in ('ATCODER', 'GEEKSFORGEEKS', 'OTHER'):
        op.execute(f"ALTER TYPE coding_platform ADD VALUE IF NOT EXISTS '{label}'")

    op.add_column(
        'coding_platform_accounts',
        sa.Column('custom_platform_name', sa.String(length=60), nullable=True),
    )

    # --- 3. projects: demo link, claimed stack, nominated project ----------
    op.add_column('projects', sa.Column('live_demo_url', sa.String(length=500), nullable=True))
    op.add_column(
        'projects',
        sa.Column(
            'claimed_technologies',
            sa.ARRAY(sa.String(length=60)),
            nullable=False,
            server_default='{}',
        ),
    )
    op.add_column(
        'projects',
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # The server defaults exist only to fill existing rows; the application
    # always supplies both, and leaving them would let a future insert that
    # forgets the column look correct.
    op.alter_column('projects', 'claimed_technologies', server_default=None)
    op.alter_column('projects', 'is_primary', server_default=None)

    # --- 4. certificates: the uploaded file --------------------------------
    op.add_column('certificates', sa.Column('file_object_key', sa.String(length=500), nullable=True))
    op.add_column('certificates', sa.Column('file_name', sa.String(length=255), nullable=True))
    op.add_column('certificates', sa.Column('file_content_type', sa.String(length=100), nullable=True))
    op.add_column('certificates', sa.Column('file_size_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('certificates', 'file_size_bytes')
    op.drop_column('certificates', 'file_content_type')
    op.drop_column('certificates', 'file_name')
    op.drop_column('certificates', 'file_object_key')

    op.drop_column('projects', 'is_primary')
    op.drop_column('projects', 'claimed_technologies')
    op.drop_column('projects', 'live_demo_url')

    op.drop_column('coding_platform_accounts', 'custom_platform_name')
    op.drop_column('candidate_profiles', 'verification_summary_sent_at')
    op.drop_column('candidate_profiles', 'onboarding_submitted_at')

    # The three enum labels are not removed, for the reason `e4c92a17f8d3`
    # documents: Postgres cannot drop a single label, and a row still carrying
    # one would be orphaned by dropping the type rather than saved by it.

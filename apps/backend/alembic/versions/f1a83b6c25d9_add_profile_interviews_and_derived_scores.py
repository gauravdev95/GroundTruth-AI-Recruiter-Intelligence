"""add profile interviews, rubric versioning, and derived candidate scores

Four changes, all additive:

1. **`candidate_profiles.evidence_score` / `.interview_score`.** `profile_strength`
   stays what it was — completeness, which cannot fall when a worker rejects a
   claim. The two new columns carry the facts it deliberately does not: how
   strong the *verified* evidence is (this one can and should fall), and the
   candidate's aggregate AI interview score. Three questions, three numbers —
   collapsing them would make each unanswerable.

   `evidence_score` is NOT NULL DEFAULT 0 because "no verified evidence" is a
   fact about a candidate, not missing data. `interview_score` **is** nullable:
   "has not been interviewed" and "was interviewed and scored 0" are different
   facts, and the discoverability gate reads presence while the match score
   reads value.

2. **`interviews.project_id` becomes nullable**, gated by a new
   `interviews.grounding` discriminator (`REPOSITORY` | `PROFILE`). A profile
   interview is scoped to the candidate rather than to one repository, and
   exists so a candidate with no verifiable repository still has a route to a
   completed interview — which discoverability now requires. Without it,
   anyone GitHub cannot verify would be permanently undiscoverable with no
   action available to them.

   The column is backfilled to `REPOSITORY` before the NOT NULL is applied:
   every interview that exists today is repository-grounded by construction,
   since profile interviews did not exist until this revision.

3. **`interviews.rubric_version`**, defaulted to 1 for existing rows and 2 for
   new ones. The rubric weights are now operator-configurable and the dimension
   set changed from four to five, but an evidence report is written once and
   never edited — so an interview keeps rendering and explaining the rubric it
   was actually scored under. Existing rows are v1 and stay v1; nothing is
   retroactively rescored against a rubric the candidate never sat.

The `interviews.total_score` values already stored remain valid: they were
computed under v1 weights that summed to 1.0, on the same 0-100 scale v2 uses.

Revision ID: f1a83b6c25d9
Revises: e4c92a17f8d3
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f1a83b6c25d9'
down_revision: Union[str, None] = 'e4c92a17f8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Created explicitly with `create_type=False` on the column reference, for the
# same reason `c3f1a9d47b02` and `f7a41c9d3e58` do it: SQLAlchemy otherwise
# emits an implicit CREATE TYPE at first use, which raises DuplicateObject if
# the type is referenced more than once.
_GROUNDING_NAME = 'interview_grounding'
_GROUNDING_LABELS = ('REPOSITORY', 'PROFILE')


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. derived candidate scores ---------------------------------------
    op.add_column(
        'candidate_profiles',
        sa.Column('evidence_score', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'candidate_profiles',
        sa.Column('interview_score', sa.Numeric(5, 2), nullable=True),
    )
    # Drop the server default now that every existing row has a value. The
    # application always supplies it (`completeness.apply_completeness`), and
    # leaving a DB-side default would let a future INSERT that forgets the
    # column look correct instead of failing.
    op.alter_column('candidate_profiles', 'evidence_score', server_default=None)

    # --- 2. interview grounding --------------------------------------------
    grounding = postgresql.ENUM(*_GROUNDING_LABELS, name=_GROUNDING_NAME)
    grounding.create(bind, checkfirst=True)

    grounding_ref = postgresql.ENUM(name=_GROUNDING_NAME, create_type=False)
    op.add_column('interviews', sa.Column('grounding', grounding_ref, nullable=True))
    # Every pre-existing interview is repository-grounded by construction.
    op.execute("UPDATE interviews SET grounding = 'REPOSITORY' WHERE grounding IS NULL")
    op.alter_column('interviews', 'grounding', nullable=False)
    op.create_index('ix_interviews_grounding', 'interviews', ['grounding'])

    # Nullable only for PROFILE interviews. The "REPOSITORY implies a project"
    # rule is enforced in `interview/service.py` rather than as a CHECK, so it
    # reports as a domain error rather than an opaque DB failure.
    op.alter_column('interviews', 'project_id', existing_type=postgresql.UUID(), nullable=True)

    # --- 3. rubric version --------------------------------------------------
    op.add_column(
        'interviews',
        sa.Column('rubric_version', sa.Integer(), nullable=False, server_default='1'),
    )
    # New rows default to the current rubric in application code; the server
    # default of 1 exists only to backfill the rows written before this
    # revision, so it is dropped immediately afterwards.
    op.alter_column('interviews', 'rubric_version', server_default=None)


def downgrade() -> None:
    op.drop_column('interviews', 'rubric_version')

    # Profile interviews have no project and cannot satisfy a NOT NULL
    # project_id. They are deleted rather than silently re-pointed at an
    # unrelated repository: a downgrade past this revision removes the feature
    # that created them, and inventing a project for an interview that was
    # never about one would corrupt the evidence trail.
    op.execute("DELETE FROM interviews WHERE grounding = 'PROFILE'")
    op.alter_column('interviews', 'project_id', existing_type=postgresql.UUID(), nullable=False)

    op.drop_index('ix_interviews_grounding', table_name='interviews')
    op.drop_column('interviews', 'grounding')
    postgresql.ENUM(name=_GROUNDING_NAME).drop(op.get_bind(), checkfirst=True)

    op.drop_column('candidate_profiles', 'interview_score')
    op.drop_column('candidate_profiles', 'evidence_score')

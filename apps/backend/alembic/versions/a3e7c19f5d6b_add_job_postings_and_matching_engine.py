"""add job postings, job requirements, embeddings, and match results

Three things:

1. **Job postings** (`job_postings`, `job_requirements`) — the recruiter side
   of the task. `job_requirements` reuses the existing `skills` table and
   `proficiency_level` enum (already created by `48b43c88a821`) rather than
   inventing a parallel skill vocabulary, so a candidate's `candidate_skills`
   row and a job's `job_requirements` row can be joined directly.

2. **Embeddings** (`embeddings`) — the polymorphic vector store
   `docs/DATA_MODEL.md` §6 designed, serving both `candidate_profile` and
   `job_posting` entities from one table. `pgvector` (the Postgres
   extension) is already enabled by `infra/docker/postgres/init.sql`; this
   migration is what actually creates a column using it, plus an `ivfflat`
   approximate-nearest-neighbor index (chosen over `hnsw` for broader
   pgvector-extension-version compatibility — `ivfflat` has been available
   since pgvector 0.1.0). `lists=100` is a starting value tuned for a
   dataset in the low tens of thousands of rows; revisit per pgvector's own
   sizing guidance (`lists = rows / 1000` for larger datasets) once real
   volume exists.

3. **Match results** (`match_results`) — the persisted output of the rank-
   fusion pipeline (`domains/matching/scoring.py`), one row per
   `(job_posting, candidate)` pair that cleared the match threshold. Both
   the recruiter's ranked list and the student's job feed read this table
   directly; neither computes anything at request time.

`companies` gets no schema change — it already exists
(`48b43c88a821`), unused. This migration's application-code counterpart
(`domains/auth/service.py::register_recruiter`) is what starts writing to it.

Revision ID: a3e7c19f5d6b
Revises: d8b3f61a9c02
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3e7c19f5d6b'
down_revision: Union[str, None] = 'd8b3f61a9c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


job_status = postgresql.ENUM(
    'DRAFT', 'EXTRACTING', 'AWAITING_CONFIRMATION', 'PUBLISHED', 'CLOSED',
    name='job_status',
    create_type=False,
)
job_type = postgresql.ENUM(
    'FULL_TIME', 'PART_TIME', 'INTERNSHIP', 'CONTRACT', name='job_type', create_type=False
)
experience_level = postgresql.ENUM(
    'ENTRY', 'MID', 'SENIOR', name='experience_level', create_type=False
)
embeddable_entity_type = postgresql.ENUM(
    'CANDIDATE_PROFILE', 'JOB_POSTING', name='embeddable_entity_type', create_type=False
)
# Already created by 48b43c88a821 — referenced, not (re)created, here.
proficiency_level = postgresql.ENUM(name='proficiency_level', create_type=False)

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    bind = op.get_bind()

    job_status.create(bind, checkfirst=True)
    job_type.create(bind, checkfirst=True)
    experience_level.create(bind, checkfirst=True)
    embeddable_entity_type.create(bind, checkfirst=True)

    # --- Job postings ---------------------------------------------------
    op.create_table(
        'job_postings',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('job_type', job_type, nullable=False),
        sa.Column('experience_level', experience_level, nullable=False),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('is_remote', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('status', job_status, nullable=False, server_default='DRAFT'),
        sa.Column('extracted_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_error', sa.Text(), nullable=True),
        sa.Column('embedding_text', sa.Text(), nullable=True),
        sa.Column('needs_reembedding', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('job_postings', 'is_remote', server_default=None)
    op.alter_column('job_postings', 'status', server_default=None)
    op.alter_column('job_postings', 'needs_reembedding', server_default=None)
    op.create_index(op.f('ix_job_postings_company_id'), 'job_postings', ['company_id'], unique=False)
    op.create_index(
        op.f('ix_job_postings_created_by_user_id'), 'job_postings', ['created_by_user_id'], unique=False
    )
    op.create_index(op.f('ix_job_postings_location'), 'job_postings', ['location'], unique=False)
    op.create_index(op.f('ix_job_postings_status'), 'job_postings', ['status'], unique=False)

    op.create_table(
        'job_requirements',
        sa.Column('job_posting_id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('min_proficiency', proficiency_level, nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False, server_default='1'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_posting_id', 'skill_id', name='uq_job_requirement_skill'),
    )
    op.alter_column('job_requirements', 'weight', server_default=None)
    op.alter_column('job_requirements', 'is_required', server_default=None)
    op.create_index(
        op.f('ix_job_requirements_job_posting_id'), 'job_requirements', ['job_posting_id'], unique=False
    )
    op.create_index(op.f('ix_job_requirements_skill_id'), 'job_requirements', ['skill_id'], unique=False)

    # --- Embeddings -------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'embeddings',
        sa.Column('entity_type', embeddable_entity_type, nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('vector', postgresql.ARRAY(sa.Float()), nullable=False),  # placeholder, altered below
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'model_version', name='uq_embedding_entity_model'),
    )
    # `pgvector`'s SQLAlchemy type isn't a plain built-in, so the column is
    # created as a placeholder above and swapped to `vector(1536)` here via
    # raw DDL — avoids importing the `pgvector` package into a migration
    # file, which otherwise pins this migration to whatever version happens
    # to be installed when it runs.
    op.execute("ALTER TABLE embeddings DROP COLUMN vector")
    op.execute(f"ALTER TABLE embeddings ADD COLUMN vector vector({EMBEDDING_DIMENSIONS}) NOT NULL")
    op.create_index(
        'ix_embeddings_entity', 'embeddings', ['entity_type', 'entity_id'], unique=False
    )
    op.execute(
        "CREATE INDEX ix_embeddings_vector_ann ON embeddings "
        "USING ivfflat (vector vector_cosine_ops) WITH (lists = 100)"
    )

    # --- Match results ------------------------------------------------------
    op.create_table(
        'match_results',
        sa.Column('job_posting_id', sa.UUID(), nullable=False),
        sa.Column('candidate_profile_id', sa.UUID(), nullable=False),
        sa.Column('match_score', sa.Numeric(5, 2), nullable=False),
        sa.Column('semantic_score', sa.Numeric(6, 5), nullable=False),
        sa.Column('evidence_score', sa.Numeric(6, 5), nullable=False),
        sa.Column('profile_strength_at_match', sa.Integer(), nullable=False),
        sa.Column('matched_required_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('matched_desirable_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_posting_id', 'candidate_profile_id', name='uq_match_result_pair'),
    )
    op.create_index(
        op.f('ix_match_results_job_posting_id'), 'match_results', ['job_posting_id'], unique=False
    )
    op.create_index(
        op.f('ix_match_results_candidate_profile_id'), 'match_results', ['candidate_profile_id'], unique=False
    )
    op.create_index(op.f('ix_match_results_match_score'), 'match_results', ['match_score'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f('ix_match_results_match_score'), table_name='match_results')
    op.drop_index(op.f('ix_match_results_candidate_profile_id'), table_name='match_results')
    op.drop_index(op.f('ix_match_results_job_posting_id'), table_name='match_results')
    op.drop_table('match_results')

    op.execute('DROP INDEX IF EXISTS ix_embeddings_vector_ann')
    op.drop_index('ix_embeddings_entity', table_name='embeddings')
    op.drop_table('embeddings')

    op.drop_index(op.f('ix_job_requirements_skill_id'), table_name='job_requirements')
    op.drop_index(op.f('ix_job_requirements_job_posting_id'), table_name='job_requirements')
    op.drop_table('job_requirements')

    op.drop_index(op.f('ix_job_postings_status'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_location'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_created_by_user_id'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_company_id'), table_name='job_postings')
    op.drop_table('job_postings')

    embeddable_entity_type.drop(bind, checkfirst=True)
    experience_level.drop(bind, checkfirst=True)
    job_type.drop(bind, checkfirst=True)
    job_status.drop(bind, checkfirst=True)

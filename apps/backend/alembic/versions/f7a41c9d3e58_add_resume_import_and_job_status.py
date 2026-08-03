"""add resume uploads, extraction drafts, and async_jobs status columns

Adds the DRAFT table LLM output lands in (`resume_extraction_drafts`), the
uploaded-file record (`resume_uploads`), and the columns the UI needs to poll a
background job (`async_jobs.celery_task_id`, `started_at`, `finished_at`,
`dead_lettered_at`).

`dead_lettered_at` is what makes the dead-letter queue a query rather than a
separate table: `status = 'FAILED' AND dead_lettered_at IS NOT NULL`.

Hand-written for the same reason as `c3f1a9d47b02`: enums are created once,
explicitly, with `create_type=False` on every column reference, because
SQLAlchemy otherwise emits an implicit CREATE TYPE at first use.

Revision ID: f7a41c9d3e58
Revises: c3f1a9d47b02
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f7a41c9d3e58'
down_revision: Union[str, None] = 'c3f1a9d47b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


resume_upload_status = postgresql.ENUM(
    'UPLOADED', 'PROCESSING', 'EXTRACTED', 'FAILED',
    name='resume_upload_status',
    create_type=False,
)
resume_draft_status = postgresql.ENUM(
    'PENDING_REVIEW', 'CONFIRMED', 'DISCARDED',
    name='resume_draft_status',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    resume_upload_status.create(bind, checkfirst=True)
    resume_draft_status.create(bind, checkfirst=True)

    # --- Job status columns the UI polls ---
    op.add_column('async_jobs', sa.Column('celery_task_id', sa.String(length=155), nullable=True))
    op.add_column('async_jobs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('async_jobs', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('async_jobs', sa.Column('dead_lettered_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_async_jobs_celery_task_id'), 'async_jobs', ['celery_task_id'], unique=False)
    op.create_index(
        op.f('ix_async_jobs_dead_lettered_at'), 'async_jobs', ['dead_lettered_at'], unique=False
    )

    # --- Uploaded resume files ---
    op.create_table(
        'resume_uploads',
        sa.Column('candidate_profile_id', sa.UUID(), nullable=False),
        sa.Column('object_key', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', resume_upload_status, nullable=False),
        sa.Column('async_job_id', sa.UUID(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        # SET NULL, not CASCADE: job rows are operational and may be pruned,
        # but losing one must not delete the student's upload.
        sa.ForeignKeyConstraint(['async_job_id'], ['async_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_resume_uploads_candidate_profile_id'),
        'resume_uploads',
        ['candidate_profile_id'],
        unique=False,
    )
    op.create_index(op.f('ix_resume_uploads_status'), 'resume_uploads', ['status'], unique=False)
    op.create_index(
        op.f('ix_resume_uploads_async_job_id'), 'resume_uploads', ['async_job_id'], unique=False
    )

    # --- Extraction drafts: where LLM output lands, never a live profile table ---
    op.create_table(
        'resume_extraction_drafts',
        sa.Column('resume_upload_id', sa.UUID(), nullable=False),
        sa.Column('candidate_profile_id', sa.UUID(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('status', resume_draft_status, nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_selection', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resume_upload_id'], ['resume_uploads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_resume_extraction_drafts_resume_upload_id'),
        'resume_extraction_drafts',
        ['resume_upload_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_resume_extraction_drafts_candidate_profile_id'),
        'resume_extraction_drafts',
        ['candidate_profile_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_resume_extraction_drafts_status'),
        'resume_extraction_drafts',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f('ix_resume_extraction_drafts_status'), table_name='resume_extraction_drafts')
    op.drop_index(
        op.f('ix_resume_extraction_drafts_candidate_profile_id'),
        table_name='resume_extraction_drafts',
    )
    op.drop_index(
        op.f('ix_resume_extraction_drafts_resume_upload_id'), table_name='resume_extraction_drafts'
    )
    op.drop_table('resume_extraction_drafts')

    op.drop_index(op.f('ix_resume_uploads_async_job_id'), table_name='resume_uploads')
    op.drop_index(op.f('ix_resume_uploads_status'), table_name='resume_uploads')
    op.drop_index(op.f('ix_resume_uploads_candidate_profile_id'), table_name='resume_uploads')
    op.drop_table('resume_uploads')

    op.drop_index(op.f('ix_async_jobs_dead_lettered_at'), table_name='async_jobs')
    op.drop_index(op.f('ix_async_jobs_celery_task_id'), table_name='async_jobs')
    for column in ('dead_lettered_at', 'finished_at', 'started_at', 'celery_task_id'):
        op.drop_column('async_jobs', column)

    resume_draft_status.drop(bind, checkfirst=True)
    resume_upload_status.drop(bind, checkfirst=True)

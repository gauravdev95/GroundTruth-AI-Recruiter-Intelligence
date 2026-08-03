"""add applications, conversations, messages, notifications, recruiter_notes

The marketplace loop: `applications` (Smart Apply's output and the Kanban
pipeline's rows), `conversations`/`messages` (in-platform messaging,
restricted to pairs with an application between them), `notifications`
(stage-change and new-message alerts), and `recruiter_notes` (private,
company-scoped).

`audit_log` gets no schema change — it already exists (`48b43c88a821`),
unused until this revision's application-code counterpart
(`core/audit.py`, wired into `jobs/tasks/verification.py` and
`domains/pipeline/service.py`) starts writing to it.

Revision ID: c7f2a94e6b1d
Revises: a3e7c19f5d6b
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c7f2a94e6b1d'
down_revision: Union[str, None] = 'a3e7c19f5d6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


application_status = postgresql.ENUM(
    'APPLIED', 'SHORTLISTED', 'INTERVIEW_SCHEDULED', 'HIRED', 'REJECTED',
    name='application_status',
    create_type=False,
)
notification_type = postgresql.ENUM(
    'STAGE_CHANGE', 'NEW_MESSAGE', name='notification_type', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    application_status.create(bind, checkfirst=True)
    notification_type.create(bind, checkfirst=True)

    op.create_table(
        'applications',
        sa.Column('job_posting_id', sa.UUID(), nullable=False),
        sa.Column('candidate_profile_id', sa.UUID(), nullable=False),
        sa.Column('status', application_status, nullable=False, server_default='APPLIED'),
        sa.Column('cover_note', sa.Text(), nullable=True),
        sa.Column('evidence_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_posting_id', 'candidate_profile_id', name='uq_application_pair'),
    )
    op.alter_column('applications', 'status', server_default=None)
    op.alter_column('applications', 'evidence_snapshot', server_default=None)
    op.create_index(op.f('ix_applications_job_posting_id'), 'applications', ['job_posting_id'], unique=False)
    op.create_index(
        op.f('ix_applications_candidate_profile_id'), 'applications', ['candidate_profile_id'], unique=False
    )
    op.create_index(op.f('ix_applications_status'), 'applications', ['status'], unique=False)

    op.create_table(
        'conversations',
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id'),
    )

    op.create_table(
        'messages',
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender_user_id', sa.UUID(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('type', notification_type, nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('notifications', 'payload', server_default=None)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    op.create_table(
        'recruiter_notes',
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('author_user_id', sa.UUID(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recruiter_notes_application_id'), 'recruiter_notes', ['application_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f('ix_recruiter_notes_application_id'), table_name='recruiter_notes')
    op.drop_table('recruiter_notes')

    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')

    op.drop_table('conversations')

    op.drop_index(op.f('ix_applications_status'), table_name='applications')
    op.drop_index(op.f('ix_applications_candidate_profile_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_job_posting_id'), table_name='applications')
    op.drop_table('applications')

    notification_type.drop(bind, checkfirst=True)
    application_status.drop(bind, checkfirst=True)

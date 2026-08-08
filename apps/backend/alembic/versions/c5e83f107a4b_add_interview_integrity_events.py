"""add interview integrity events

The video interview room can observe things the typed one could not: a tab
losing visibility, a camera track ending, fullscreen being exited, a long
stretch with no speech. This table is where those observations go.

**It is a new table and nothing else.** No column is added to `interviews`, no
existing table is touched, and no scoring path reads from here — an interview
scored before this revision and the same interview scored after it produce
identical numbers. That separation is the point: these describe the conditions
an interview was taken in, not what the candidate said, and the two must not be
able to contaminate each other.

`(interview_id, client_sequence)` is unique so the room's flush can be
at-least-once. It flushes on a timer, on `visibilitychange` and on unload, and
the last of those genuinely fires twice on some browsers — without the
constraint, closing a laptop lid would double a candidate's event counts.

`event_type` is a plain string, not a native enum, matching
`interview_verification_flags.status`. The vocabulary is expected to grow as the
room learns to notice more, and the validation boundary is
`schemas.py::IntegrityEventType`, so an unknown value is a 422 rather than a row.

Revision ID: c5e83f107a4b
Revises: a2d75e13c9f4
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c5e83f107a4b'
down_revision: Union[str, None] = 'a2d75e13c9f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_integrity_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_sequence', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('elapsed_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'interview_id', 'client_sequence', name='uq_interview_integrity_sequence'
        ),
    )
    op.create_index(
        op.f('ix_interview_integrity_events_interview_id'),
        'interview_integrity_events',
        ['interview_id'],
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_interview_integrity_events_interview_id'),
        table_name='interview_integrity_events',
    )
    op.drop_table('interview_integrity_events')

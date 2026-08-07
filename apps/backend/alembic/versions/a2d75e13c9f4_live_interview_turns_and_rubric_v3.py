"""replace the typed interview with the live conversational one

The typed interview asked five to seven questions, took one answer each, and
scored each answer in isolation. The live interview holds a conversation:
follow-ups, bridges, continuous claim verification, one scoring pass over the
whole transcript. That is a different shape of record, so this migration
replaces the tables rather than extending them.

**Nothing is thrown away.** `interview_answers` and `interview_scores` are
dropped, but only after their contents are carried into the new tables:

* Each question and its answer become two `interview_turns` rows — an
  interviewer turn holding the question as it was put, then the candidate's
  reply — in the order they were asked. A typed interview therefore reads back
  as exactly what it was: a stiff conversation where the interviewer never
  followed up.
* Per-answer rubric scores become one `interview_dimension_scores` row per
  dimension, averaged across the answers, carrying the weights they were
  actually scored under. The stored `interviews.total_score` is *not*
  recomputed: it was correct under its own rubric, and averaging the parts back
  into a headline would risk quietly changing a number a candidate has already
  been shown.

Old interviews keep `rubric_version` 1 or 2 and keep rendering under the frozen
weights in `domains/interview/models.py`. Only interviews started after this
revision are v3.

Two columns on `interview_questions` go away — `time_limit_seconds` and
`presented_at`. Both belonged to a per-question clock that no longer exists:
the live interview has one session clock, on `interviews.time_limit_seconds`.

Revision ID: a2d75e13c9f4
Revises: b9e2f45c81a7
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a2d75e13c9f4'
down_revision: Union[str, None] = 'b9e2f45c81a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Created explicitly with `create_type=False` on the column reference, for the
# same reason the earlier interview revisions do it: SQLAlchemy otherwise emits
# an implicit CREATE TYPE at first use, which raises DuplicateObject if the
# type is referenced more than once.
_STAGE_NAME = 'interview_stage'
_STAGE_LABELS = ('WARMUP', 'MAIN', 'WRAPUP', 'DONE')
_ROLE_NAME = 'interview_turn_role'
_ROLE_LABELS = ('INTERVIEWER', 'CANDIDATE')
_COMFORT_NAME = 'candidate_comfort'
_COMFORT_LABELS = ('CONFIDENT', 'NEUTRAL', 'NERVOUS')

#: The session clock every pre-existing interview is given. Ten minutes, the
#: configured default — these interviews are finished, so the value is only
#: ever read to render a report, never to time anybody.
_DEFAULT_TIME_LIMIT = '600'


def upgrade() -> None:
    bind = op.get_bind()

    stage = postgresql.ENUM(*_STAGE_LABELS, name=_STAGE_NAME)
    stage.create(bind, checkfirst=True)
    role = postgresql.ENUM(*_ROLE_LABELS, name=_ROLE_NAME)
    role.create(bind, checkfirst=True)
    comfort = postgresql.ENUM(*_COMFORT_LABELS, name=_COMFORT_NAME)
    comfort.create(bind, checkfirst=True)

    stage_ref = postgresql.ENUM(name=_STAGE_NAME, create_type=False)
    comfort_ref = postgresql.ENUM(name=_COMFORT_NAME, create_type=False)
    role_ref = postgresql.ENUM(name=_ROLE_NAME, create_type=False)

    # --- 1. live session state on the interview -----------------------------
    op.add_column('interviews', sa.Column('stage', stage_ref, nullable=True))
    # Every interview that exists today is over, or was abandoned mid-typing
    # with no conversation to resume. DONE is the honest stage for both: the
    # live session cannot pick either of them up.
    op.execute("UPDATE interviews SET stage = 'DONE' WHERE stage IS NULL")
    op.alter_column('interviews', 'stage', nullable=False)

    op.add_column(
        'interviews',
        sa.Column('current_question_index', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'interviews', sa.Column('follow_up_count', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'interviews',
        sa.Column(
            'time_limit_seconds', sa.Integer(), nullable=False, server_default=_DEFAULT_TIME_LIMIT
        ),
    )
    op.add_column('interviews', sa.Column('candidate_comfort', comfort_ref, nullable=True))
    op.execute("UPDATE interviews SET candidate_comfort = 'NEUTRAL' WHERE candidate_comfort IS NULL")
    op.alter_column('interviews', 'candidate_comfort', nullable=False)

    # Drop the server defaults now that every existing row has a value. The
    # application always supplies these, and leaving DB-side defaults would let
    # a future INSERT that forgets one look correct instead of failing.
    op.alter_column('interviews', 'current_question_index', server_default=None)
    op.alter_column('interviews', 'follow_up_count', server_default=None)
    op.alter_column('interviews', 'time_limit_seconds', server_default=None)

    # --- 2. expected signals on the questions --------------------------------
    op.add_column(
        'interview_questions',
        sa.Column('expected_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # --- 3. the conversation --------------------------------------------------
    op.create_table(
        'interview_turns',
        sa.Column('interview_id', sa.UUID(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('role', role_ref, nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=True),
        sa.Column('question_index', sa.Integer(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('spoken_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_id', 'sequence', name='uq_interview_turn_sequence'),
    )
    op.create_index(
        op.f('ix_interview_turns_interview_id'), 'interview_turns', ['interview_id'], unique=False
    )

    op.create_table(
        'interview_verification_flags',
        sa.Column('interview_id', sa.UUID(), nullable=False),
        sa.Column('turn_id', sa.UUID(), nullable=True),
        sa.Column('claim', sa.Text(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='none'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        # SET NULL, not CASCADE: verification history must not be deletable by
        # way of the turn that produced it.
        sa.ForeignKeyConstraint(['turn_id'], ['interview_turns.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_interview_verification_flags_interview_id'),
        'interview_verification_flags',
        ['interview_id'],
        unique=False,
    )
    op.alter_column('interview_verification_flags', 'severity', server_default=None)

    op.create_table(
        'interview_dimension_scores',
        sa.Column('interview_id', sa.UUID(), nullable=False),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False),
        sa.Column('score', sa.Numeric(5, 2), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        # 0-100, the same scale as `score` — see
        # `ai/interview_schema.py::DimensionScore.confidence`.
        sa.Column('confidence', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_id', 'dimension', name='uq_interview_dimension_score'),
    )
    op.create_index(
        op.f('ix_interview_dimension_scores_interview_id'),
        'interview_dimension_scores',
        ['interview_id'],
        unique=False,
    )
    op.alter_column('interview_dimension_scores', 'confidence', server_default=None)

    # --- 4. carry the typed interviews across ---------------------------------
    # Question, then answer, in question order. `ord` breaks the tie inside one
    # question so the interviewer's turn always precedes the candidate's.
    op.execute(
        """
        INSERT INTO interview_turns (
            id, interview_id, sequence, role, text, action, question_index,
            internal_notes, spoken_at, created_at
        )
        SELECT
            gen_random_uuid(),
            src.interview_id,
            row_number() OVER (PARTITION BY src.interview_id ORDER BY src.q_sequence, src.ord),
            src.role::interview_turn_role,
            src.text,
            src.action,
            src.q_sequence - 1,
            NULL,
            src.ts,
            src.ts
        FROM (
            SELECT
                q.interview_id,
                q.sequence AS q_sequence,
                turn.role,
                turn.text,
                turn.action,
                turn.ord,
                turn.ts
            FROM interview_questions q
            LEFT JOIN interview_answers a ON a.interview_question_id = q.id
            CROSS JOIN LATERAL (
                VALUES
                    ('INTERVIEWER', q.prompt, 'ASK_QUESTION', 1,
                     COALESCE(q.presented_at, q.created_at)),
                    ('CANDIDATE', a.transcript, NULL, 2,
                     COALESCE(a.answered_at, q.presented_at, q.created_at))
            ) AS turn(role, text, action, ord, ts)
            WHERE turn.text IS NOT NULL
        ) AS src
        """
    )

    # One row per dimension per interview, averaged across that interview's
    # answers — which is what the old `total_score` already summarised, so the
    # two agree by construction.
    op.execute(
        """
        INSERT INTO interview_dimension_scores (
            id, interview_id, dimension, weight, score, evidence, confidence, created_at
        )
        SELECT
            gen_random_uuid(),
            q.interview_id,
            s.dimension,
            MAX(s.weight),
            ROUND(AVG(s.score), 2),
            'Carried over from the per-answer scores of a pre-conversational interview.',
            100.0,
            MIN(s.created_at)
        FROM interview_scores s
        JOIN interview_answers a ON a.id = s.interview_answer_id
        JOIN interview_questions q ON q.id = a.interview_question_id
        GROUP BY q.interview_id, s.dimension
        """
    )

    # --- 5. drop what the live interview replaced -----------------------------
    op.drop_index(op.f('ix_interview_scores_interview_answer_id'), table_name='interview_scores')
    op.drop_table('interview_scores')
    op.drop_table('interview_answers')
    op.drop_column('interview_questions', 'time_limit_seconds')
    op.drop_column('interview_questions', 'presented_at')


def downgrade() -> None:
    bind = op.get_bind()

    # The typed tables come back empty. A conversation cannot be folded back
    # into one-answer-per-question without inventing which follow-up belonged
    # to which answer, and a downgrade that guesses at interview evidence is
    # worse than one that admits the shape changed.
    op.add_column(
        'interview_questions',
        sa.Column('presented_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'interview_questions',
        sa.Column('time_limit_seconds', sa.Integer(), nullable=False, server_default='300'),
    )
    op.alter_column('interview_questions', 'time_limit_seconds', server_default=None)

    op.create_table(
        'interview_answers',
        sa.Column('interview_question_id', sa.UUID(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('time_taken_seconds', sa.Integer(), nullable=True),
        sa.Column('exceeded_time_limit', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['interview_question_id'], ['interview_questions.id'], ondelete='CASCADE'),
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
        sa.ForeignKeyConstraint(['interview_answer_id'], ['interview_answers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_interview_scores_interview_answer_id'),
        'interview_scores',
        ['interview_answer_id'],
        unique=False,
    )

    op.drop_index(
        op.f('ix_interview_dimension_scores_interview_id'), table_name='interview_dimension_scores'
    )
    op.drop_table('interview_dimension_scores')
    op.drop_index(
        op.f('ix_interview_verification_flags_interview_id'),
        table_name='interview_verification_flags',
    )
    op.drop_table('interview_verification_flags')
    op.drop_index(op.f('ix_interview_turns_interview_id'), table_name='interview_turns')
    op.drop_table('interview_turns')

    op.drop_column('interview_questions', 'expected_signals')
    op.drop_column('interviews', 'candidate_comfort')
    op.drop_column('interviews', 'time_limit_seconds')
    op.drop_column('interviews', 'follow_up_count')
    op.drop_column('interviews', 'current_question_index')
    op.drop_column('interviews', 'stage')

    postgresql.ENUM(name=_COMFORT_NAME).drop(bind, checkfirst=True)
    postgresql.ENUM(name=_ROLE_NAME).drop(bind, checkfirst=True)
    postgresql.ENUM(name=_STAGE_NAME).drop(bind, checkfirst=True)

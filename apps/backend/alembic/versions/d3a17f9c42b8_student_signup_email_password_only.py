"""Make users.full_name nullable for email + password student signup.

Student registration now takes an email and a password and nothing else;
the name is collected in the first onboarding section instead. This relaxes
the NOT NULL so a student row can exist between those two points.

REVERSIBILITY, AND THE ONE THING THE DOWNGRADE CANNOT DO

`upgrade` is a pure relaxation — every existing row already satisfies the
looser constraint, so it cannot fail and cannot lose data.

`downgrade` has to re-tighten a column that may by then contain NULLs, and
there is no honest value to backfill them with. Deriving a name from the
email local part would write invented personal data into a user record,
which is exactly the kind of fabrication this platform exists to avoid, and
it would persist after the downgrade as though the user had supplied it.

So the downgrade backfills the empty string and says so. `""` is visibly a
placeholder rather than a plausible name, `User.display_name` already treats
it as absent (it is falsy), and anything reading the column directly gets
something obviously wrong rather than something subtly wrong. If this
downgrade is ever run in anger, those rows are identifiable with
`WHERE full_name = ''`.

Revision ID: d3a17f9c42b8
Revises: c8d2f47a91e6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3a17f9c42b8"
down_revision: Union[str, None] = "c8d2f47a91e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=200),
        nullable=True,
    )


def downgrade() -> None:
    # Must run before the constraint is re-applied, or the ALTER fails on any
    # student who signed up and has not yet saved their first section.
    op.execute("UPDATE users SET full_name = '' WHERE full_name IS NULL")
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=200),
        nullable=False,
    )

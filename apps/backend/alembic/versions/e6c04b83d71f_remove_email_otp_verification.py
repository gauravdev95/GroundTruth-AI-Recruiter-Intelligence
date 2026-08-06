"""Remove the email OTP verification system.

Signup now creates a usable account directly: no 6-digit code, no
`/verify-email/*` endpoints, no verification screen between the form and
the product. This drops the two pieces of schema that existed only to
serve that flow.

WHY THE COLUMN GOES TOO, AND NOT JUST THE TABLE

`email_verification_tokens` is unambiguously dead — nothing issues or
consumes an OTP any more. `users.is_email_verified` is the closer call,
because it is a plausible-sounding column that some future feature might
want. It is dropped anyway: with the OTP flow gone, the only code path
that could ever set it to `true` was Google OAuth copying the provider's
`email_verified` claim, and the login gate that read it is gone as well.
What remains is a column named "verified" that is `false` for every
password account forever and that nothing reads — a stored claim the
product cannot support, which is the specific failure mode this codebase
is built to avoid. Re-introducing verification later means adding a
mechanism, and a mechanism can bring its own column back with a meaning
that is true on the day it lands.

REVERSIBILITY

`upgrade` destroys data: every outstanding OTP row and every per-user
verified flag. That is the point of it, and it cannot be undone by
`downgrade` — a downgrade can only rebuild the shapes.

`downgrade` recreates the table empty and re-adds the column defaulted to
`true` rather than `false`. `false` is the "safer-looking" default and is
the wrong one here: after this migration every account in the table has
been able to log in without verifying anything, so restoring the old
login gate with `false` would lock out the entire user base at once,
including accounts created long before this change. `true` restores the
column with the only value consistent with the access those accounts
actually have. The server-side default is then dropped, so rows created
after the downgrade go back to the original `false`-by-application
behaviour.

Revision ID: e6c04b83d71f
Revises: d3a17f9c42b8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6c04b83d71f"
down_revision: Union[str, None] = "d3a17f9c42b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "is_email_verified")


def downgrade() -> None:
    # `server_default` fills existing rows in the same statement that adds the
    # NOT NULL column; without it the ALTER fails on any non-empty table. See
    # the module docstring for why the fill value is `true`.
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.alter_column("users", "is_email_verified", server_default=None)

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
    )

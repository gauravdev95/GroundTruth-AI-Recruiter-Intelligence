"""add candidate about, CodeChef platform, and three employment types

Three additive changes, no rewrites:

1. **`candidate_profiles.about`** — a free-text self-summary. Nullable, and
   deliberately **not** added to `completeness._BASIC_FIELDS`: that tuple's
   length divides `BASIC_POINTS` exactly (35 / 7 = 5), so an eighth field would
   make section 1 unable to reach its own maximum and silently cap every
   profile below 100. Scoring it is a separate, breaking change.

2. **`coding_platform` gains `CODECHEF`.** Like HackerRank, CodeChef exposes no
   usable public API (its documented one was retired), so the verification task
   checks it by URL reachability and it caps at `FLAGGED` — see
   `jobs/tasks/verification.py`.

3. **`employment_type` gains `FULL_TIME`, `RESEARCH`, `OPEN_SOURCE`.**

`ALTER TYPE ... ADD VALUE` is legal inside Alembic's single migration
transaction here for the same reason it was in `d8b3f61a9c02`: Postgres forbids
*using* a new enum label in the transaction that added it, not adding it, and
nothing below INSERTs or UPDATEs a row with one of these labels.

Enum labels are the Python member **names** (`FULL_TIME`), not the values
(`full_time`) — SQLAlchemy's `SAEnum(..., native_enum=True)` stores names, as
every prior migration in this tree does.

Revision ID: e4c92a17f8d3
Revises: b2d5e8f14c73
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4c92a17f8d3'
down_revision: Union[str, None] = 'b2d5e8f14c73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. candidate_profiles.about ---------------------------------------
    op.add_column('candidate_profiles', sa.Column('about', sa.Text(), nullable=True))

    # --- 2. coding_platform: add CODECHEF ----------------------------------
    op.execute("ALTER TYPE coding_platform ADD VALUE IF NOT EXISTS 'CODECHEF'")

    # --- 3. employment_type: three new shapes of work ----------------------
    for label in ('FULL_TIME', 'RESEARCH', 'OPEN_SOURCE'):
        op.execute(f"ALTER TYPE employment_type ADD VALUE IF NOT EXISTS '{label}'")


def downgrade() -> None:
    op.drop_column('candidate_profiles', 'about')

    # The four enum labels are not removed. Postgres cannot drop a single enum
    # label (only the whole type), and `coding_platform_accounts` /
    # `experiences` still reference both types. Leaving them is harmless:
    # nothing below this revision writes them, and a row that *does* carry one
    # would be orphaned by a label drop rather than saved by it.

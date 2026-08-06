"""Add multi-role targeting, a profile photo, and a recorded onboarding consent.

Three additions to `candidate_profiles`, all driven by the eight-stage
student onboarding flow.

TARGET ROLES: A NEW ARRAY BESIDE THE EXISTING ENUM, NOT A REPLACEMENT

Onboarding now collects one to three target roles instead of one. The
obvious move is to widen `target_role` into an array and delete the scalar,
and it is the wrong one here: `target_role` is a native PG enum with an
index, and `matching/`, `pipeline/evidence.py` and the recruiter evidence
card all read and filter on it. Widening it would turn a vocabulary change
into a rewrite of the matching pre-filter.

So `target_roles` is added as the full preference set and `target_role`
stays as the **primary** role — always `target_roles[0]`, written in the
same statement by the single writer (`student/service.py::replace_basic_info`),
so the two cannot drift. Existing readers keep working unchanged and get
the same answer they got before; the new readers that care about the whole
set read the array.

The array is `String(40)`, not an array of the native enum, matching how
`projects.technologies` and `experiences.technologies` already store
controlled lists in this schema. The vocabulary is enforced at the API
boundary by `TargetRole` on the Pydantic model, and the scalar mirror keeps
a DB-level enum check on the primary value.

Backfill is exact: every profile with a `target_role` gets a one-element
array holding it, so no profile's stated preference changes.

CONSENT IS NOT BACKFILLED, DELIBERATELY

`onboarding_consent_at` records the DPDP consent checkbox on the review
step. Profiles that submitted before this migration have no value and do
not get one.

Setting it to their `onboarding_submitted_at` would be the convenient
choice and it would be a fabricated consent record — writing down that
someone agreed to repository analysis on a date when they were never asked.
A consent log that contains entries nobody made is worse than one with
gaps, because the gaps are the honest part.

Nothing breaks as a result: `submit_onboarding` returns early and
idempotently for an already-submitted profile, so the new gate is only ever
evaluated for a submission that has not happened yet. Already-onboarded
students are unaffected and are never asked again.

REVERSIBILITY

`downgrade` drops all four columns. It destroys the consent log and any
uploaded photo keys (the objects themselves outlive it in storage and are
orphaned). `target_role` is untouched throughout, so a downgrade loses only
the second and third role a student chose, never their primary one.

Revision ID: b9e2f45c81a7
Revises: e6c04b83d71f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9e2f45c81a7"
down_revision: Union[str, None] = "e6c04b83d71f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("target_roles", postgresql.ARRAY(sa.String(length=40)), nullable=True),
    )
    # Object key only. The bucket is configuration and the content type is
    # sniffed from the file's own leading bytes on upload, never taken from the
    # request — same rule `student/certificate_files.py` applies.
    op.add_column(
        "candidate_profiles",
        sa.Column("profile_photo_object_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("profile_photo_content_type", sa.String(length=100), nullable=True),
    )
    # A timestamp rather than a boolean, for the same reason
    # `onboarding_submitted_at` is: consent is an act that happened at a moment,
    # and "when" is the part a consent log has to be able to answer.
    op.add_column(
        "candidate_profiles",
        sa.Column("onboarding_consent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Cast through text: `target_role` is a native enum and the destination is
    # a text array, so the enum label is what lands in the array element.
    op.execute(
        """
        UPDATE candidate_profiles
           SET target_roles = ARRAY[target_role::text]
         WHERE target_role IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "onboarding_consent_at")
    op.drop_column("candidate_profiles", "profile_photo_content_type")
    op.drop_column("candidate_profiles", "profile_photo_object_key")
    op.drop_column("candidate_profiles", "target_roles")

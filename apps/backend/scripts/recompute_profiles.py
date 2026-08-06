"""One-off backfill: recompute every candidate's derived state.

**Run this once after migrating to `f1a83b6c25d9`.**

That migration adds `evidence_score` and `interview_score` and changes what
`is_discoverable` means, but a migration can only supply column defaults — it
cannot run the scoring logic, which lives in `domains/student/completeness.py`
and reads rows across five tables. Without this script the post-migration state
is quietly wrong rather than obviously broken:

* `interview_score` is NULL even for candidates who have completed interviews,
  so the interview term of their match score silently contributes zero;
* `evidence_score` is 0 for everyone, including fully verified candidates;
* `is_discoverable` still reflects the old two-stage gate, so candidates who
  have never been interviewed stay visible to recruiters;
* `match_results` still hold scores computed under the previous formula and
  threshold, so both feeds show numbers no current code would produce.

Recomputing the profile fixes the first three directly. The fourth follows,
because `recompute_and_persist_strength` re-syncs the matching index for every
profile it touches (`student/service.py::_sync_matching_index`).

Idempotent — it derives everything from stored rows and writes no new state, so
running it twice is a no-op. Safe to run on a live database, though it does
re-embed and re-match, so expect worker load proportional to the candidate
count.

    uv run python -m scripts.recompute_profiles [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from src.db import register_models  # noqa: F401 — mapper configuration
from src.db.database import SessionLocal
from src.domains.auth.models import CandidateProfile
from src.domains.student import service as student_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        profile_ids = list(db.execute(select(CandidateProfile.id)).scalars())
        print(f"Recomputing {len(profile_ids)} candidate profile(s)...")

        changed = 0
        for profile_id in profile_ids:
            profile = db.get(CandidateProfile, profile_id)
            if profile is None:
                continue

            before = (
                profile.profile_strength,
                profile.evidence_score,
                float(profile.interview_score) if profile.interview_score is not None else None,
                profile.is_discoverable,
            )

            if args.dry_run:
                # Compute without persisting: `compute_completeness` is pure,
                # so this reports the delta without touching the row.
                completeness = student_service.compute_completeness(
                    student_service.load_snapshot(db, profile)
                )
                after = (
                    completeness.profile_strength,
                    completeness.evidence_score,
                    completeness.interview_score,
                    completeness.is_discoverable,
                )
            else:
                # `sync_matching_index=True` (the default) is what re-embeds and
                # re-scores this candidate's pairs under the current formula and
                # threshold — the reason stale `match_results` heal here too.
                completeness = student_service.recompute_and_persist_strength(db, profile_id)
                if completeness is None:
                    continue
                after = (
                    completeness.profile_strength,
                    completeness.evidence_score,
                    completeness.interview_score,
                    completeness.is_discoverable,
                )

            if before != after:
                changed += 1
                print(
                    f"  {profile_id}: strength {before[0]}->{after[0]} "
                    f"evidence {before[1]}->{after[1]} "
                    f"interview {before[2]}->{after[2]} "
                    f"discoverable {before[3]}->{after[3]}"
                )

        verb = "would change" if args.dry_run else "changed"
        print(f"\n{changed} profile(s) {verb}.")
        if args.dry_run:
            print("Dry run — nothing was written.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

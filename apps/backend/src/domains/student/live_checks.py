"""Synchronous existence checks behind the "Verify" buttons on setup step 3.

These run **inside the request** and write nothing. That is the whole design,
and it is what keeps them compatible with the async verification they sit in
front of:

* `jobs/tasks/verification.py` owns every durable `verification_status`. It
  runs minutes later, retries, and its verdicts are audited. Nothing here may
  write one, so a button press can never manufacture a `VERIFIED` row.
* These answer one narrower question — *does this account exist right now* —
  so the student is not allowed to save a typo'd handle and discover it hours
  later from an email. `student/router.py` requires a `verified` or
  `unconfirmed` outcome before the technical section saves.

The outcome vocabulary (`VerifyOutcome`) is deliberately not
`VerificationStatus` for the same reason: three values about a live probe, not
five about a stored claim.

**Why some platforms can only ever be `unconfirmed`.** Codeforces has a
documented API and LeetCode an undocumented GraphQL endpoint, so both can
confirm a handle exists. HackerRank, CodeChef, AtCoder, GeeksforGeeks and
`OTHER` expose nothing usable, so the check is URL reachability — which proves
the page resolves, not that the candidate owns it. Reporting that as
"verified" would be the single most misleading thing this file could do.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_verification_settings
from src.domains.student.models import CodingPlatform, GithubAccount
from src.domains.student.schemas import VerifyOutcome, build_coding_platform_url
from src.domains.verification.clients import codeforces as codeforces_client
from src.domains.verification.clients import github as github_client
from src.domains.verification.clients import leetcode as leetcode_client
from src.domains.verification.clients import reachability
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GithubCheck:
    outcome: VerifyOutcome
    message: str
    github_username: str
    profile_url: str
    avatar_url: str | None = None
    public_repos: int | None = None
    is_oauth_connected: bool = False


@dataclass(frozen=True)
class CodingProfileCheck:
    outcome: VerifyOutcome
    message: str
    platform: CodingPlatform
    handle: str
    profile_url: str
    details: dict = field(default_factory=dict)


def check_github(db: Session, *, candidate_profile_id: uuid.UUID, username: str) -> GithubCheck:
    """Confirm a GitHub username resolves to a real account.

    If this candidate has already connected *this* username via OAuth, that is
    reported instead of re-checking: OAuth proved ownership, which no API
    lookup here can, and re-running the weaker check would present the weaker
    result as the current one.
    """
    profile_url = f"https://github.com/{username}"

    connected = db.execute(
        select(GithubAccount).where(
            GithubAccount.candidate_profile_id == candidate_profile_id,
            GithubAccount.deleted_at.is_(None),
            GithubAccount.oauth_connected_at.is_not(None),
        )
    ).scalar_one_or_none()

    if connected is not None and connected.github_username.casefold() == username.casefold():
        return GithubCheck(
            outcome=VerifyOutcome.VERIFIED,
            message="Connected with GitHub — ownership confirmed.",
            github_username=connected.github_username,
            profile_url=connected.profile_url,
            is_oauth_connected=True,
        )

    try:
        user = github_client.get_user(username)
    except ClaimNotFound:
        return GithubCheck(
            outcome=VerifyOutcome.FAILED,
            message=f"No GitHub account named “{username}”. Check the spelling.",
            github_username=username,
            profile_url=profile_url,
        )
    except VerificationServiceUnavailable as exc:
        # Not a failed *claim* — a failed *check*. Said plainly so the student
        # retries rather than assuming their own username is wrong.
        logger.warning("github_live_check_unavailable", username=username, error=str(exc))
        return GithubCheck(
            outcome=VerifyOutcome.FAILED,
            message="GitHub could not be reached just now. Try again in a moment.",
            github_username=username,
            profile_url=profile_url,
        )

    return GithubCheck(
        # `verified` here means the account exists, not that this student owns
        # it — connecting via OAuth is what proves that, and the UI keeps
        # offering it. See the module docstring.
        outcome=VerifyOutcome.VERIFIED,
        message=f"Found github.com/{user['login']}.",
        github_username=user["login"],
        profile_url=user.get("html_url") or profile_url,
        avatar_url=user.get("avatar_url"),
        public_repos=user.get("public_repos"),
    )


#: Reachability budget per platform, for the ones with no API. Keyed by
#: platform so adding a member without a bucket is a `KeyError` in tests rather
#: than an unbounded fetch loop in production.
def _reachability_budget(platform: CodingPlatform) -> int:
    settings = get_verification_settings()
    return {
        CodingPlatform.HACKERRANK: settings.hackerrank_rate_limit_per_minute,
        CodingPlatform.CODECHEF: settings.codechef_rate_limit_per_minute,
        CodingPlatform.ATCODER: settings.atcoder_rate_limit_per_minute,
        CodingPlatform.GEEKSFORGEEKS: settings.geeksforgeeks_rate_limit_per_minute,
        CodingPlatform.OTHER: settings.other_platform_rate_limit_per_minute,
    }[platform]


def check_coding_profile(
    *, platform: CodingPlatform, handle: str, custom_url: str | None = None
) -> CodingProfileCheck:
    """Confirm a competitive-programming handle exists, as far as the platform
    allows. See the module docstring for why most can only be `unconfirmed`."""
    profile_url = build_coding_platform_url(platform, handle, custom_url=custom_url)

    try:
        if platform is CodingPlatform.CODEFORCES:
            info = codeforces_client.get_user_info(handle)
            return CodingProfileCheck(
                outcome=VerifyOutcome.VERIFIED,
                message=f"Found {info.get('handle', handle)} on Codeforces.",
                platform=platform,
                handle=handle,
                profile_url=profile_url,
                details={
                    "rating": info.get("rating"),
                    "max_rating": info.get("maxRating"),
                    "rank": info.get("rank"),
                },
            )

        if platform is CodingPlatform.LEETCODE:
            stats = leetcode_client.get_user_stats(handle)
            solved = leetcode_client.total_solved(stats)
            return CodingProfileCheck(
                outcome=VerifyOutcome.VERIFIED,
                message=f"Found {stats.get('username', handle)} on LeetCode.",
                platform=platform,
                handle=handle,
                profile_url=profile_url,
                details={"solved_count": solved, "ranking": (stats.get("profile") or {}).get("ranking")},
            )

        reachable, _body = reachability.check_reachable(
            profile_url,
            rate_limit_name=f"{platform.value}_live",
            max_requests_per_minute=_reachability_budget(platform),
        )
        if not reachable:
            return CodingProfileCheck(
                outcome=VerifyOutcome.FAILED,
                message="That profile page could not be found. Check the handle.",
                platform=platform,
                handle=handle,
                profile_url=profile_url,
            )
        return CodingProfileCheck(
            # Never `verified`: the page resolving says the profile exists, not
            # that this candidate owns it, and this platform gives us no way to
            # tell the difference.
            outcome=VerifyOutcome.UNCONFIRMED,
            message="Profile page found. This platform has no public API, so ownership can't be confirmed.",
            platform=platform,
            handle=handle,
            profile_url=profile_url,
            details={"confidence": "low"},
        )

    except ClaimNotFound:
        return CodingProfileCheck(
            outcome=VerifyOutcome.FAILED,
            message=f"No profile found for “{handle}” on this platform.",
            platform=platform,
            handle=handle,
            profile_url=profile_url,
        )
    except VerificationServiceUnavailable as exc:
        logger.warning(
            "coding_profile_live_check_unavailable",
            platform=platform.value,
            handle=handle,
            error=str(exc),
        )
        return CodingProfileCheck(
            outcome=VerifyOutcome.FAILED,
            message="That platform could not be reached just now. Try again in a moment.",
            platform=platform,
            handle=handle,
            profile_url=profile_url,
        )

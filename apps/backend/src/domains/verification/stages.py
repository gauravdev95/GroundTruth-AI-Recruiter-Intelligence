"""The seven-stage repository verification pipeline.

Repository verification used to be one Celery task that fetched everything,
computed everything, and wrote a single `Project.verification_payload` blob at
the end. That had two problems worth fixing rather than documenting:

1. **A late failure discarded early success.** If technology detection raised
   after the fork check and contribution analysis had already completed, the
   whole run was lost and the retry started from nothing. Nobody could see how
   far it had got, or why.
2. **"Stage" was not a thing that existed.** The analysis moved through
   distinct phases, but only in the sense that the code ran top to bottom —
   there was no way to ask "did the authorship check pass?" without parsing
   the final blob, and no way for a stage to be *skipped* as opposed to
   failed.

Each stage now persists its own `verification_stages` row: status, result,
error, and timings. A stage does not start unless its predecessor
`SUCCEEDED`, and when one fails the rest are marked `SKIPPED` rather than
left to look pending forever.

**Stage ownership.** This module runs stages 1-5 — everything derivable from
the GitHub API — and writes the composite verdict. The last two belong to
flows that a background task cannot drive on its own:

* `CODE_GROUNDED_INTERVIEW` is student-initiated (`domains/interview/`), so
  this pipeline only opens the gate: it leaves the stage `PENDING` when the
  repository verified, and `SKIPPED` when it did not.
* `EVIDENCE_REPORT` completes when the interview evaluation writes its report.

**Authorship is a hard gate.** If stage 2 concludes the candidate did not
author the repository, the repository is not verified and stages 6-7 are
skipped — no interview is generated for a repository we do not believe is
theirs, which is the whole point of grounding interview questions in code the
candidate actually wrote.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.student.models import (
    STAGE_SEQUENCE,
    VerificationStage,
    VerificationStageKind,
    VerificationStageStatus,
)
from src.domains.verification import manifests, scoring
from src.domains.verification.clients import github as github_client
from src.domains.verification.exceptions import ClaimNotFound

logger = structlog.get_logger(__name__)

# How much of the file tree is retained on the project payload for the
# interview to ground questions in. The full tree can be thousands of entries;
# the question generator needs a representative slice, not an inventory.
FILE_PATH_SAMPLE_SIZE = 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StageFailed(Exception):
    """A stage reached a definite negative conclusion — as opposed to failing
    to reach one. Raised by the authorship gate, never by a network error:
    a timeout means "unknown", which must be retried, not recorded as a
    verdict."""

    def __init__(self, message: str, *, verdict: scoring.RepositoryVerdict) -> None:
        super().__init__(message)
        self.verdict = verdict


@dataclass
class RepositoryContext:
    """Carries state between stages so no stage refetches what an earlier one
    already has. `contributor_stats` in particular is one of the slowest
    GitHub calls and is used by both the authorship gate and contribution
    analysis."""

    project_id: uuid.UUID
    candidate_profile_id: uuid.UUID
    repo_url: str
    github_login: str | None
    token: str | None

    owner: str = ""
    repo: str = ""
    is_fork: bool = False
    default_branch: str = "main"
    primary_language: str | None = None

    attribution_login: str = ""
    contributor_stats: list[dict] = field(default_factory=list)
    contribution_share: float = 0.0
    weekly_commit_counts: list[int] = field(default_factory=list)

    file_paths: list[str] = field(default_factory=list)
    has_tests: bool = False
    quality_score: float = 0.0

    detected_technologies: list = field(default_factory=list)

    authenticity_score: float = 0.0
    composite_score: float = 0.0
    verdict: scoring.RepositoryVerdict | None = None


# --------------------------------------------------------------------------
# Stage row bookkeeping
# --------------------------------------------------------------------------


def ensure_stage_rows(db: Session, project_id: uuid.UUID) -> dict[VerificationStageKind, VerificationStage]:
    """Creates the seven rows for a project if they don't exist, and resets
    them to `PENDING` for a re-run.

    A re-verification is a fresh run of the whole pipeline, so leaving a
    previous run's `SUCCEEDED`/`FAILED` statuses in place would make the gate
    ("previous stage succeeded") pass against stale history. Results are
    cleared with the statuses for the same reason — a result belongs to the
    run that produced it.
    """
    existing = {
        row.stage: row
        for row in db.execute(
            select(VerificationStage).where(VerificationStage.project_id == project_id)
        ).scalars()
    }

    for index, kind in enumerate(STAGE_SEQUENCE):
        row = existing.get(kind)
        if row is None:
            row = VerificationStage(
                project_id=project_id,
                stage=kind,
                sequence=index + 1,
                status=VerificationStageStatus.PENDING,
            )
            db.add(row)
            existing[kind] = row
        else:
            row.sequence = index + 1
            row.status = VerificationStageStatus.PENDING
            row.result = None
            row.error = None
            row.started_at = None
            row.completed_at = None

    db.flush()
    return existing


def _mark_running(db: Session, row: VerificationStage) -> None:
    row.status = VerificationStageStatus.RUNNING
    row.started_at = _utcnow()
    row.error = None
    db.commit()


def _mark_succeeded(db: Session, row: VerificationStage, result: dict[str, Any]) -> None:
    row.status = VerificationStageStatus.SUCCEEDED
    row.result = result
    row.completed_at = _utcnow()
    row.error = None
    db.commit()


def _mark_failed(db: Session, row: VerificationStage, error: str) -> None:
    row.status = VerificationStageStatus.FAILED
    row.error = error
    row.completed_at = _utcnow()
    db.commit()


def _mark_pending(db: Session, row: VerificationStage) -> None:
    """Returns a stage to the queue after a transient failure. Deliberately
    not `FAILED`: the retry re-runs the pipeline from the top, and a stage
    left `FAILED` would make the gate refuse to reach it again."""
    row.status = VerificationStageStatus.PENDING
    row.started_at = None
    db.commit()


def _skip_from(
    db: Session,
    rows: dict[VerificationStageKind, VerificationStage],
    *,
    after: VerificationStageKind,
    reason: str,
) -> None:
    """Marks every stage after `after` as `SKIPPED`. Skipped is not failed:
    these stages never ran, and reporting them as failures would attribute a
    problem to code that was never executed."""
    start = STAGE_SEQUENCE.index(after) + 1
    for kind in STAGE_SEQUENCE[start:]:
        row = rows[kind]
        if row.status in (VerificationStageStatus.PENDING, VerificationStageStatus.RUNNING):
            row.status = VerificationStageStatus.SKIPPED
            row.error = reason
            row.completed_at = _utcnow()
    db.commit()


# --------------------------------------------------------------------------
# The stages themselves
# --------------------------------------------------------------------------


def _stage_repository_selection(ctx: RepositoryContext) -> dict[str, Any]:
    """Resolves the claimed URL to a real repository and reads its metadata."""
    ctx.owner, ctx.repo = github_client.parse_repo_url(ctx.repo_url)
    repo_info = github_client.get_repo(ctx.owner, ctx.repo, token=ctx.token)

    ctx.is_fork = bool(repo_info.get("fork"))
    ctx.default_branch = repo_info.get("default_branch", "main")
    ctx.primary_language = repo_info.get("language")

    return {
        "owner": ctx.owner,
        "repo": ctx.repo,
        "is_fork": ctx.is_fork,
        "default_branch": ctx.default_branch,
        "primary_language": ctx.primary_language,
        "stars": repo_info.get("stargazers_count"),
        "created_at": repo_info.get("created_at"),
    }


def _stage_fork_authorship_check(ctx: RepositoryContext) -> dict[str, Any]:
    """The gate. Establishes whether this repository is the candidate's work
    at all, before anything downstream spends time analysing it.

    A candidate with no connected GitHub account has only their claim that the
    repo owner is them. That claim is taken at face value *for attribution
    purposes only* — it decides whose commits to count, and a wrong guess
    yields a near-zero share and fails here, so it grants no undue credit.
    """
    ctx.attribution_login = ctx.github_login or ctx.owner
    ctx.contributor_stats = github_client.get_contributor_stats(ctx.owner, ctx.repo, token=ctx.token)
    ctx.contribution_share = scoring.compute_contribution_share(
        ctx.contributor_stats, ctx.attribution_login
    )
    ctx.authenticity_score = scoring.compute_authenticity_score(
        is_fork=ctx.is_fork, contribution_share=ctx.contribution_share
    )

    result = {
        "attribution_login": ctx.attribution_login,
        "is_fork": ctx.is_fork,
        "contribution_share": ctx.contribution_share,
        "authenticity_score": ctx.authenticity_score,
        "contributor_count": len(ctx.contributor_stats),
    }

    if ctx.contribution_share < scoring.CONTRIBUTION_REJECT_THRESHOLD:
        verdict = scoring.RepositoryVerdict(
            status="rejected",
            reason=(
                f"Contribution share {ctx.contribution_share:.1%} is below the "
                f"{scoring.CONTRIBUTION_REJECT_THRESHOLD:.0%} threshold — the candidate does not "
                "appear to be a meaningful contributor to this repository."
            ),
        )
        result["passed"] = False
        result["reason"] = verdict.reason
        raise StageFailed(verdict.reason, verdict=verdict)

    if ctx.is_fork and ctx.contribution_share < scoring.FORK_LOW_CONTRIBUTION_THRESHOLD:
        verdict = scoring.RepositoryVerdict(
            status="flagged",
            reason=(
                f"This is a fork and the candidate's contribution share "
                f"({ctx.contribution_share:.1%}) is below "
                f"{scoring.FORK_LOW_CONTRIBUTION_THRESHOLD:.0%} — not enough divergence from "
                "upstream to credit as original work."
            ),
        )
        result["passed"] = False
        result["reason"] = verdict.reason
        raise StageFailed(verdict.reason, verdict=verdict)

    result["passed"] = True
    return result


def _stage_contribution_analysis(ctx: RepositoryContext) -> dict[str, Any]:
    """Quantifies the contribution the previous stage established exists —
    commit cadence over time, and the per-contributor breakdown behind the
    share. Reuses `ctx.contributor_stats` rather than refetching."""
    commit_activity = github_client.get_commit_activity(ctx.owner, ctx.repo, token=ctx.token)
    ctx.weekly_commit_counts = [int(week.get("total", 0) or 0) for week in commit_activity]

    active_weeks = sum(1 for count in ctx.weekly_commit_counts if count > 0)
    top_contributors = sorted(
        (
            {
                "login": (entry.get("author") or {}).get("login"),
                "commits": int(entry.get("total", 0) or 0),
            }
            for entry in ctx.contributor_stats
        ),
        key=lambda entry: entry["commits"],
        reverse=True,
    )[:5]

    return {
        "contribution_share": ctx.contribution_share,
        "total_commits": sum(int(e.get("total", 0) or 0) for e in ctx.contributor_stats),
        "active_weeks": active_weeks,
        "weekly_commit_counts": ctx.weekly_commit_counts,
        "top_contributors": top_contributors,
    }


def _stage_architecture_code_quality(ctx: RepositoryContext) -> dict[str, Any]:
    """Structural signals: how large the codebase is, whether it has tests,
    and whether the commit history looks maintained rather than dumped."""
    ctx.file_paths = github_client.get_repo_tree(
        ctx.owner, ctx.repo, ctx.default_branch, token=ctx.token
    )
    ctx.has_tests = manifests.has_test_files(ctx.file_paths)
    ctx.quality_score = scoring.compute_quality_score(
        has_tests=ctx.has_tests,
        file_count=len(ctx.file_paths),
        weekly_commit_counts=ctx.weekly_commit_counts,
    )

    return {
        "file_count": len(ctx.file_paths),
        "has_tests": ctx.has_tests,
        "quality_score": ctx.quality_score,
        # The slice the interview's question generator grounds itself in.
        "file_paths_sample": ctx.file_paths[:FILE_PATH_SAMPLE_SIZE],
    }


def _stage_technology_detection(ctx: RepositoryContext) -> dict[str, Any]:
    """Reads dependency manifests — not a language guess from file
    extensions — so a detected technology traces back to a declared
    dependency."""
    ctx.detected_technologies = manifests.detect_technologies(
        ctx.file_paths,
        lambda path: github_client.get_file_content(ctx.owner, ctx.repo, path, token=ctx.token),
        primary_language=ctx.primary_language,
    )
    return {
        "detected_technologies": [t.name for t in ctx.detected_technologies],
        "primary_language": ctx.primary_language,
    }


#: Stages 1-5, in order, with the function that runs each. Stages 6 and 7 are
#: driven by the interview flow — see the module docstring.
ANALYSIS_STAGES: tuple[tuple[VerificationStageKind, Callable[[RepositoryContext], dict[str, Any]]], ...] = (
    (VerificationStageKind.REPOSITORY_SELECTION, _stage_repository_selection),
    (VerificationStageKind.FORK_AUTHORSHIP_CHECK, _stage_fork_authorship_check),
    (VerificationStageKind.CONTRIBUTION_ANALYSIS, _stage_contribution_analysis),
    (VerificationStageKind.ARCHITECTURE_CODE_QUALITY, _stage_architecture_code_quality),
    (VerificationStageKind.TECHNOLOGY_DETECTION, _stage_technology_detection),
)


@dataclass(frozen=True)
class PipelineOutcome:
    """What the caller needs to write onto the `Project` row. `verdict` is
    `None` only when the run ended without reaching a conclusion — a transient
    failure — which is the case where the claim must be left alone for a
    retry rather than recorded as any status."""

    verdict: scoring.RepositoryVerdict | None
    composite_score: float
    payload: dict[str, Any]
    failed_stage: VerificationStageKind | None = None


def run_analysis_pipeline(
    db: Session, ctx: RepositoryContext, *, is_final_attempt: bool
) -> PipelineOutcome:
    """Runs stages 1-5 in order, persisting each.

    Three ways a run ends:

    * **All five succeed** — a composite verdict is computed, and the
      interview stage is left `PENDING` (open) if the repository verified.
    * **The authorship gate rejects** (`StageFailed`) — a real verdict, so the
      stage is recorded `FAILED` with the reason, everything after it is
      `SKIPPED`, and no interview is generated.
    * **Something transient breaks** — the exception propagates so Celery's
      retry ladder handles it. On the last attempt the stage is recorded
      `FAILED`; before that it goes back to `PENDING`, because the retry
      re-runs from stage 1 and a `FAILED` predecessor would block the gate.
    """
    rows = ensure_stage_rows(db, ctx.project_id)
    db.commit()

    payload: dict[str, Any] = {"repo_url": ctx.repo_url, "stages": {}}

    for kind, run_stage in ANALYSIS_STAGES:
        row = rows[kind]
        _mark_running(db, row)

        try:
            result = run_stage(ctx)
        except ClaimNotFound as exc:
            # Definite, not transient: the repository does not exist or is not
            # reachable as claimed. Recorded as a real stage failure and never
            # retried into success, unlike a timeout.
            _mark_failed(db, row, str(exc))
            _skip_from(db, rows, after=kind, reason=f"{kind.value} failed: {exc}")
            logger.info(
                "verification_stage_claim_not_found",
                project_id=str(ctx.project_id),
                stage=kind.value,
                error=str(exc),
            )
            raise
        except StageFailed as exc:
            _mark_failed(db, row, str(exc))
            _skip_from(db, rows, after=kind, reason=f"{kind.value} did not pass")
            payload["stages"][kind.value] = {"status": "failed", "reason": str(exc)}
            logger.info(
                "verification_stage_gate_failed",
                project_id=str(ctx.project_id),
                stage=kind.value,
                reason=str(exc),
            )
            return PipelineOutcome(
                verdict=exc.verdict,
                composite_score=0.0,
                payload=payload,
                failed_stage=kind,
            )
        except Exception as exc:
            if is_final_attempt:
                _mark_failed(db, row, str(exc))
                _skip_from(db, rows, after=kind, reason=f"{kind.value} failed")
            else:
                _mark_pending(db, row)
            logger.warning(
                "verification_stage_errored",
                project_id=str(ctx.project_id),
                stage=kind.value,
                error=str(exc),
                final_attempt=is_final_attempt,
            )
            raise

        _mark_succeeded(db, row, result)
        payload["stages"][kind.value] = {"status": "succeeded", **result}

    ctx.composite_score = scoring.score_repository(
        contribution_share=ctx.contribution_share,
        quality_score=ctx.quality_score,
        authenticity_score=ctx.authenticity_score,
    )
    ctx.verdict = scoring.decide_repository_status(
        contribution_share=ctx.contribution_share, is_fork=ctx.is_fork, score=ctx.composite_score
    )

    if ctx.verdict.status != "verified":
        # Analysis completed, but the repository did not clear the bar. The
        # interview is grounded in verified work only, so it never opens.
        _skip_from(
            db,
            rows,
            after=VerificationStageKind.TECHNOLOGY_DETECTION,
            reason=f"Repository {ctx.verdict.status}: {ctx.verdict.reason}",
        )

    payload.update(
        {
            "owner": ctx.owner,
            "repo": ctx.repo,
            "is_fork": ctx.is_fork,
            "contribution_share": ctx.contribution_share,
            "quality_score": ctx.quality_score,
            "authenticity_score": ctx.authenticity_score,
            "has_tests": ctx.has_tests,
            "file_count": len(ctx.file_paths),
            "detected_technologies": [t.name for t in ctx.detected_technologies],
            "reason": ctx.verdict.reason,
            "file_paths_sample": ctx.file_paths[:FILE_PATH_SAMPLE_SIZE],
        }
    )

    return PipelineOutcome(verdict=ctx.verdict, composite_score=ctx.composite_score, payload=payload)


# --------------------------------------------------------------------------
# Stages 6 and 7, driven by the interview flow
# --------------------------------------------------------------------------


def _set_stage(
    db: Session,
    project_id: uuid.UUID,
    kind: VerificationStageKind,
    *,
    status: VerificationStageStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> VerificationStage | None:
    row = db.execute(
        select(VerificationStage).where(
            VerificationStage.project_id == project_id, VerificationStage.stage == kind
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    row.status = status
    if result is not None:
        row.result = result
    row.error = error
    if status is VerificationStageStatus.RUNNING and row.started_at is None:
        row.started_at = _utcnow()
    if status in (
        VerificationStageStatus.SUCCEEDED,
        VerificationStageStatus.FAILED,
        VerificationStageStatus.SKIPPED,
    ):
        row.completed_at = _utcnow()
    return row


def mark_interview_started(db: Session, project_id: uuid.UUID) -> None:
    _set_stage(
        db, project_id, VerificationStageKind.CODE_GROUNDED_INTERVIEW,
        status=VerificationStageStatus.RUNNING,
    )


def mark_interview_completed(
    db: Session, project_id: uuid.UUID, *, interview_id: uuid.UUID, total_score: float
) -> None:
    _set_stage(
        db, project_id, VerificationStageKind.CODE_GROUNDED_INTERVIEW,
        status=VerificationStageStatus.SUCCEEDED,
        result={"interview_id": str(interview_id), "total_score": total_score},
    )
    # The evidence report is produced by the same evaluation pass that scores
    # the interview, so the two land together rather than needing a separate
    # trigger.
    _set_stage(
        db, project_id, VerificationStageKind.EVIDENCE_REPORT,
        status=VerificationStageStatus.SUCCEEDED,
        result={"interview_id": str(interview_id), "total_score": total_score},
    )


def mark_interview_failed(db: Session, project_id: uuid.UUID, *, error: str) -> None:
    _set_stage(
        db, project_id, VerificationStageKind.CODE_GROUNDED_INTERVIEW,
        status=VerificationStageStatus.FAILED, error=error,
    )
    _set_stage(
        db, project_id, VerificationStageKind.EVIDENCE_REPORT,
        status=VerificationStageStatus.SKIPPED,
        error="Interview did not complete",
    )

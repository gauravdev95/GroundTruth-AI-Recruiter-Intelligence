"""Live AI interview API routes.

The REST routes are thin by design, matching every other router in this
codebase: parse request -> call `service` -> return a schema. Every one
resolves the profile from the authenticated candidate via `get_own_profile`,
so a recruiter is rejected with 403 before any handler body runs and no route
accepts a profile id from the client.

The socket is the interesting one. It follows `src/realtime/router.py`'s
first-frame handshake — a browser cannot set an `Authorization` header on a
WebSocket, and a `?token=` query parameter puts a live credential into every
access log — but unlike the notification socket it is *bidirectional* and
carries the conversation itself.

**The socket is a transport, not the source of truth.** Every frame it accepts
turns into exactly one `service.advance` call, and the client can rebuild the
entire session at any time from `GET /{interview_id}`. That is what makes a
dropped connection mid-answer survivable: nothing lives in the socket.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from src.config.config import get_realtime_settings
from src.core.exceptions import AppError, NotFound
from src.db.database import get_db
from src.domains.auth.dependencies import resolve_user_from_access_token
from src.domains.auth.models import CandidateProfile, UserRole
from src.domains.auth.rate_limit import limiter
from src.domains.interview import service
from src.domains.interview.schemas import (
    CandidateMessageRequest,
    EvidenceReportResponse,
    IntegrityBatchRequest,
    IntegritySummaryResponse,
    InterviewStateResponse,
    InterviewSummaryResponse,
)
from src.domains.student import service as student_service
from src.domains.student.dependencies import get_own_profile

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/student/interview", tags=["student-interview"])

# Same private-use close codes as the notification socket, plus one for a
# socket that authenticated fine but has no business on this interview.
CLOSE_AUTH_FAILED = 4401
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_FORBIDDEN = 4403

#: The floor on how quickly the interviewer answers, in seconds. A reply that
#: lands the instant the candidate stops typing reads as a lookup, not a
#: thought — so a fast turn is held back to roughly human thinking pace. There
#: is no ceiling to enforce here: the model's own latency is the ceiling, and
#: padding a slow turn further would only make a stalled interview feel worse.
MIN_RESPONSE_DELAY_SECONDS = 1.2


@router.post("/projects/{project_id}/start", response_model=InterviewSummaryResponse)
@limiter.limit("10/hour")
def start_interview(
    request: Request,
    project_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewSummaryResponse:
    interview = service.start_interview(db, profile, project_id)
    return InterviewSummaryResponse.model_validate(interview)


@router.get("/projects/{project_id}/latest", response_model=InterviewSummaryResponse)
def latest_for_project(
    project_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewSummaryResponse:
    interview = service.get_latest_for_project(db, profile, project_id)
    if interview is None:
        raise NotFound("No interview exists for this project yet")
    return InterviewSummaryResponse.model_validate(interview)


@router.get("/{interview_id}", response_model=InterviewStateResponse)
def get_state(
    interview_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewStateResponse:
    """The whole session, transcript included. This is what a reconnecting
    client reads to catch up — see the module docstring."""
    return service.get_state(db, profile, interview_id)


@router.post("/{interview_id}/turns", response_model=InterviewStateResponse)
@limiter.limit("120/hour")
def submit_turn(
    request: Request,
    interview_id: uuid.UUID,
    payload: CandidateMessageRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewStateResponse:
    """The socket's REST equivalent, kept deliberately.

    A candidate behind a proxy that eats WebSockets can still sit the whole
    interview through this route — the socket adds immediacy, not capability,
    and an interview that only works over a socket would be an interview some
    candidates simply cannot take.
    """
    return service.advance(db, profile, interview_id, message=payload.text)


@router.post("/{interview_id}/integrity", response_model=IntegritySummaryResponse)
@limiter.limit("240/hour")
def record_integrity(
    request: Request,
    interview_id: uuid.UUID,
    payload: IntegrityBatchRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> IntegritySummaryResponse:
    """Accept a batch of session-condition observations from the interview room.

    A generous limit relative to `/turns`: an interview produces far more of
    these than it produces answers, and the failure mode of a limit set too
    tight is that a candidate who alt-tabs a lot stops being *recorded* as
    alt-tabbing — the limit would suppress exactly the signal it is meant to
    protect. 240/hour is roughly one flush every fifteen seconds for the length
    of a ten-minute interview, several times over.
    """
    return service.record_integrity_events(db, profile, interview_id, payload.events)


@router.get("/{interview_id}/integrity", response_model=IntegritySummaryResponse)
def get_integrity(
    interview_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> IntegritySummaryResponse:
    """What was observed during the session.

    Its own route rather than a field on the report: integrity signals describe
    the conditions an interview was taken in, the report describes what the
    candidate said, and the two are kept apart end to end — separate table,
    separate endpoint, invisible to the Scorer.
    """
    return service.get_integrity_summary(db, profile, interview_id)


@router.get("/{interview_id}/report", response_model=EvidenceReportResponse)
def get_report(
    interview_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> EvidenceReportResponse:
    return service.get_report(db, profile, interview_id)


# ---------------------------------------------------------------------------
# The live socket
# ---------------------------------------------------------------------------


async def _authenticate(websocket: WebSocket, db: Session) -> CandidateProfile | None:
    """Resolve the candidate from a first-frame handshake.

    Duplicates `realtime/router.py`'s shape rather than importing it because
    the two resolve to different things — that one to a `user_id` for routing,
    this one to the `CandidateProfile` every call below is scoped by — and the
    role check here is load-bearing: a recruiter holding a valid token must not
    reach an interview socket at all.
    """
    settings = get_realtime_settings()
    try:
        frame = await asyncio.wait_for(
            websocket.receive_json(), timeout=settings.realtime_auth_timeout_seconds
        )
    except asyncio.TimeoutError:
        await websocket.close(code=CLOSE_AUTH_TIMEOUT, reason="Authentication timed out")
        return None
    except (WebSocketDisconnect, ValueError):
        return None

    if not isinstance(frame, dict) or frame.get("type") != "authenticate":
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="Expected an authenticate frame")
        return None

    token = frame.get("token")
    user = resolve_user_from_access_token(db, token) if isinstance(token, str) else None
    if user is None:
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="Invalid or expired token")
        return None
    if user.role is not UserRole.CANDIDATE:
        await websocket.close(code=CLOSE_FORBIDDEN, reason="Not a candidate account")
        return None

    try:
        return student_service.get_profile_for_user(db, user)
    except AppError:
        await websocket.close(code=CLOSE_FORBIDDEN, reason="No candidate profile")
        return None


async def _advance(
    websocket: WebSocket,
    db: Session,
    profile: CandidateProfile,
    interview_id: uuid.UUID,
    *,
    message: str | None,
) -> bool:
    """Run one turn and push the resulting state. False means stop reading.

    `run_in_threadpool` because `service.advance` is synchronous all the way
    down to a blocking `google-genai` call: awaiting it directly would stall
    the event loop — and therefore every other candidate's socket — for the
    length of one model round-trip.
    """
    started = time.monotonic()
    await websocket.send_json({"type": "thinking", "payload": {}})

    try:
        state = await run_in_threadpool(
            service.advance, db, profile, interview_id, message=message
        )
    except AppError as exc:
        # Domain errors are conversational here, not fatal: "you already
        # finished" or "another tab is mid-turn" are things the client should
        # show and recover from, so the socket stays open.
        await websocket.send_json(
            {"type": "error", "payload": {"code": exc.code, "message": str(exc)}}
        )
        return exc.status_code < 500
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("interview_turn_failed", interview_id=str(interview_id), error=str(exc))
        await websocket.send_json(
            {"type": "error", "payload": {"code": "INTERVIEW_TURN_FAILED", "message": "That turn could not be completed."}}
        )
        return False

    remaining_delay = MIN_RESPONSE_DELAY_SECONDS - (time.monotonic() - started)
    if remaining_delay > 0:
        await asyncio.sleep(remaining_delay)

    await websocket.send_json({"type": "state", "payload": state.model_dump(mode="json")})
    return state.interview.stage.value != "done"


@router.websocket("/{interview_id}/live")
async def live_interview_socket(
    websocket: WebSocket, interview_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """One socket per live interview session.

    The read loop is the conversation: each `candidate_message` frame is one
    turn. The server speaks first — connecting is what triggers the opener, so
    a candidate never has to say hello to a machine to make it start.
    """
    await websocket.accept()

    profile = await _authenticate(websocket, db)
    if profile is None:
        return

    try:
        state = await run_in_threadpool(service.get_state, db, profile, interview_id)
    except AppError as exc:
        await websocket.close(code=CLOSE_FORBIDDEN, reason=exc.code)
        return

    await websocket.send_json({"type": "connected", "payload": state.model_dump(mode="json")})
    logger.info("interview_socket_connected", interview_id=str(interview_id))

    # Open the interview if it has not been opened. On a reconnect the
    # transcript is already there and this is skipped — the candidate rejoins
    # a conversation rather than restarting one.
    if not state.transcript and state.interview.status.value == "in_progress":
        if not await _advance(websocket, db, profile, interview_id, message=None):
            return

    try:
        while True:
            frame = await websocket.receive_json()
            if not isinstance(frame, dict):
                continue
            if frame.get("type") == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})
                continue
            if frame.get("type") != "candidate_message":
                continue

            text = frame.get("text")
            if not isinstance(text, str) or not text.strip():
                # Silence is not a turn. Answering it would spend a model call
                # to be told the candidate said nothing.
                continue

            if not await _advance(websocket, db, profile, interview_id, message=text.strip()[:8000]):
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("interview_socket_closed", interview_id=str(interview_id), error=str(exc))
    finally:
        logger.info("interview_socket_disconnected", interview_id=str(interview_id))

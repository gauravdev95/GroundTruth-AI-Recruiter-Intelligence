"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config.config import get_security_settings
from src.core.error_handlers import register_error_handlers
from src.core.logging import configure_logging
from src.core.middleware import SecurityHeadersMiddleware
from src.core.request_id import RequestIdMiddleware
from src.db import register_models  # noqa: F401
from src.db.database import SessionLocal
from src.domains.auth.rate_limit import limiter
from src.domains.auth.router import router as auth_router
from src.domains.interview.router import router as interview_router
from src.domains.matching.router import recruiter_matches_router, student_feed_router
from src.domains.pipeline.router import notifications_router, recruiter_router as pipeline_recruiter_router, student_router as pipeline_student_router
from src.domains.recruiter.router import router as recruiter_jobs_router
from src.domains.resume.router import router as student_resume_router
from src.domains.student.github_router import router as student_github_router
from src.domains.student.router import router as student_profile_router
from src.jobs.router import router as jobs_router
from src.realtime.bus import subscriber as realtime_subscriber
from src.realtime.router import router as realtime_router

security_settings = get_security_settings()
configure_logging(debug=security_settings.app_env == "development")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Owns the realtime Redis subscriber's lifetime.

    Started here rather than lazily on the first WebSocket connection so a
    broken Redis surfaces in the startup log instead of the first time a
    student opens a dashboard — and stopped on shutdown so a reloading dev
    server doesn't leave an orphaned reader task holding a subscription.

    Note that `TestClient(app)` used as a context manager runs this too,
    which is why `tests/conftest.py`'s `client` fixture does exactly that:
    the tests exercise the same startup path production uses.
    """
    await realtime_subscriber.start()
    try:
        yield
    finally:
        await realtime_subscriber.stop()


app = FastAPI(title="GroundTruth AI", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_error_handlers(app)

configured_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
allowed_origins = [
    origin.strip()
    for origin in {*configured_origins, "https://groundtruth-ai-recruiter-intelligence-nqd5.onrender.com"}
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, hsts=security_settings.app_env == "production")
# Outermost middleware: wraps everything (including error responses) so
# every response — success or failure — carries X-Request-ID.
app.add_middleware(RequestIdMiddleware)

app.include_router(auth_router)
app.include_router(student_profile_router)
app.include_router(student_github_router)
app.include_router(student_resume_router)
app.include_router(interview_router)
app.include_router(recruiter_jobs_router)
app.include_router(recruiter_matches_router)
app.include_router(student_feed_router)
app.include_router(pipeline_student_router)
app.include_router(pipeline_recruiter_router)
app.include_router(notifications_router)
app.include_router(jobs_router)
app.include_router(realtime_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "GroundTruth AI backend is running"}


@app.get("/health")
def health_check() -> JSONResponse:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return JSONResponse({"status": "healthy", "database": "connected"})
    except SQLAlchemyError:
        return JSONResponse(
            {"status": "unhealthy", "database": "disconnected"},
            status_code=503,
        )

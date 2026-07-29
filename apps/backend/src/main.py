"""FastAPI application entrypoint.

Phase 2 mounts the authentication domain router; other domains
(student, recruiter) remain unmounted until their own phases.
"""

import os

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
from src.db.database import SessionLocal
from src.domains.auth.rate_limit import limiter
from src.domains.auth.router import router as auth_router

security_settings = get_security_settings()
configure_logging(debug=security_settings.app_env == "development")

app = FastAPI(title="GroundTruth AI")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_error_handlers(app)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, hsts=security_settings.app_env == "production")

app.include_router(auth_router)


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

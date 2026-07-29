"""SQLAlchemy database engine and session setup.

Establishes the PostgreSQL connection only — no models, tables, or
migrations are defined here.
"""

from __future__ import annotations

import sys
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.config import get_database_settings

settings = get_database_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for future ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _print_safe(message: str) -> None:
    """Print, falling back to ASCII if the console encoding can't render it."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode(sys.stdout.encoding or "ascii", errors="replace").decode())


def check_database_connection() -> bool:
    """Verify connectivity by executing SELECT 1. Never raises."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        _print_safe("✓ PostgreSQL Connected Successfully")
        return True
    except SQLAlchemyError as exc:
        print(f"PostgreSQL connection failed: {exc}")
        return False


if __name__ == "__main__":
    check_database_connection()

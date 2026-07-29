"""Shared pytest fixtures for integration tests.

Each test runs inside an outer transaction on the real configured
database (no separate test DB/infra required) that is rolled back at
teardown, even though application code calls `session.commit()`
internally — SQLAlchemy's `join_transaction_mode="create_savepoint"`
translates inner commits into savepoints instead of real commits.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.db.database import engine, get_db
from src.domains.auth.rate_limit import limiter
from src.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    limiter.reset()
    yield


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

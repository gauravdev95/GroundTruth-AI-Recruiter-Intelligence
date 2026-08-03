"""Shared pytest fixtures for integration tests.

**The test database guard runs before anything else in this file.** Every
previous test run in this project's history was collected but never
executed against a real database, because `DATABASE_URL` in `.env` points
at a live Supabase instance and nothing stopped a test run from using it.
This module makes that structurally impossible: it reads `TEST_DATABASE_URL`
(a separate, test-only variable — see `.env.example`) and overwrites the
`DATABASE_URL` environment variable with it *before* `src.db.database` (or
anything that imports it) is ever imported. `src.db.database.engine` is
built at module-import time from whatever `DATABASE_URL` resolves to at
that moment, so this ordering is load-bearing: importing `src.db.database`
even one line earlier would bind the engine to Supabase.

The hostname assertion below is the second layer: even if `TEST_DATABASE_URL`
were accidentally left unset or misconfigured to equal `DATABASE_URL`, a
hostname containing `supabase` (or anything that isn't a known local/CI
test host) hard-fails test collection rather than silently running.

Each test then runs inside an outer transaction on this test database
(rolled back at teardown, even though application code calls
`session.commit()` internally — SQLAlchemy's
`join_transaction_mode="create_savepoint"` translates inner commits into
savepoints instead of real commits) — unchanged from before; only *which*
database that transaction opens against has changed.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_TEST_HOSTS = {"localhost", "127.0.0.1", "postgres-test", "test-db", "::1"}


class _TestDatabaseSettings(BaseSettings):
    test_database_url: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def _install_test_database_url() -> None:
    try:
        test_settings = _TestDatabaseSettings()
    except Exception as exc:  # pydantic ValidationError on a missing var
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. Tests must never fall back to the "
            "application's own DATABASE_URL (which may point at a shared/production "
            "database). Set TEST_DATABASE_URL in apps/backend/.env — see .env.example "
            "and `make test-db-up`."
        ) from exc

    url = test_settings.test_database_url
    # `postgresql+psycopg://` isn't a scheme `urlparse` recognizes specially,
    # but it still parses `user:pass@host:port` correctly via the generic
    # path, so no scheme-stripping is needed for `.hostname` to work.
    hostname = (urlparse(url).hostname or "").lower()

    if "supabase" in hostname:
        raise RuntimeError(
            f"TEST_DATABASE_URL resolves to a Supabase host ('{hostname}'). "
            "Refusing to run tests against it under any circumstances."
        )
    if hostname not in _ALLOWED_TEST_HOSTS:
        raise RuntimeError(
            f"TEST_DATABASE_URL host '{hostname}' is not a recognized local/test host "
            f"({sorted(_ALLOWED_TEST_HOSTS)}). Refusing to run tests against it — if this "
            "is genuinely a disposable test host, add it to _ALLOWED_TEST_HOSTS explicitly, "
            "don't just make the check pass."
        )

    os.environ["DATABASE_URL"] = url


_install_test_database_url()

# Same reasoning as DATABASE_URL above: the test suite must never depend on
# whichever MAIL_BACKEND happens to be set in `.env` (e.g. "smtp" for real
# local dev against MailHog). `get_mail_settings()` is only read lazily
# per-call (not at import time), but pin it here anyway so it's impossible
# for a test run to attempt a real network send even if `.env` says "smtp".
os.environ["MAIL_BACKEND"] = "capture"

# Everything below this line is safe to import: `src.db.database.engine` is
# built from the now-overridden `DATABASE_URL`, which points at the test
# database, never Supabase.

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.core.mail.backends import clear_capture_outbox, get_capture_outbox  # noqa: E402
from src.db import register_models  # noqa: E402,F401 — ensures every model is mapper-configured
from src.db.database import engine, get_db  # noqa: E402
from src.domains.auth.rate_limit import limiter  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _clear_mail_outbox() -> Generator[None, None, None]:
    clear_capture_outbox()
    yield
    clear_capture_outbox()


@pytest.fixture()
def mail_outbox():
    """The in-memory `CaptureMailer` outbox (see `src/core/mail/backends.py`)
    — asserts what a test actually sent, not what it intended to send."""
    return get_capture_outbox()


@pytest.fixture(autouse=True)
def _stub_captcha(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test suite must be hermetic — it cannot depend on whether
    `RECAPTCHA_SECRET_KEY` happens to be blank in whoever's `.env` runs it.
    `captcha.verify_captcha`'s own dev-bypass (blank secret + APP_ENV=development)
    is real production behavior, not a test seam, so tests stub the call site
    directly instead of relying on incidentally-unset config. Every existing
    test already sends `captcha_token="test"` expecting exactly this — none
    test genuine reCAPTCHA rejection (that would require a real Google
    round-trip, which nothing here should ever make)."""
    monkeypatch.setattr("src.domains.auth.router.verify_captcha", lambda token, remote_ip=None: None)


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

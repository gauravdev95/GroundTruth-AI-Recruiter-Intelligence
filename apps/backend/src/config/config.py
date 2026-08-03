"""Application settings, loaded from environment variables.

One settings class per concern, each cached via `lru_cache` so the
environment is only parsed once per process — same pattern as
`DatabaseSettings`.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings sourced from the environment/.env file."""

    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return cached database settings (loaded once per process)."""
    return DatabaseSettings()


class SecuritySettings(BaseSettings):
    """App-wide secret key, JWT signing config, and cookie flags."""

    secret_key: str = "dev-secret-key-change-me"
    jwt_secret_key: str = "dev-jwt-secret-key-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    app_env: str = "development"
    frontend_base_url: str = "http://localhost:5173"
    # Symmetric key for encrypting third-party OAuth tokens at rest
    # (`GithubAccount.access_token_encrypted` — see `core/crypto.py`). Left
    # unset in dev: `core/crypto.py` derives a stable key from `secret_key`
    # instead, which is fine for local development but must be set to a real
    # generated Fernet key (`Fernet.generate_key()`) in any shared environment.
    token_encryption_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()


class CaptchaSettings(BaseSettings):
    """Google reCAPTCHA v2 site/secret keys."""

    recaptcha_site_key: str = ""
    recaptcha_secret_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_captcha_settings() -> CaptchaSettings:
    return CaptchaSettings()


class MailSettings(BaseSettings):
    """Transactional email config. `mail_backend` selects the implementation
    (`src/core/mail/backends.py`) with no code change at any call site:

    - "console": logs the message. Default — always works, zero setup.
    - "smtp": real SMTP delivery. Points at MailHog in dev/docker-compose
      (no auth/TLS needed) and a real provider in production (set
      `smtp_use_tls`/`smtp_user`/`smtp_password`).
    - "capture": in-memory outbox, used by integration tests to assert on
      sent messages (see `tests/conftest.py`'s `mail_outbox` fixture).
    """

    mail_backend: str = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_email: str = "no-reply@groundtruth.ai"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_mail_settings() -> MailSettings:
    return MailSettings()


class GoogleOAuthSettings(BaseSettings):
    """Google OAuth 2.0 Authorization Code flow credentials."""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_google_oauth_settings() -> GoogleOAuthSettings:
    return GoogleOAuthSettings()


class GitHubOAuthSettings(BaseSettings):
    """GitHub OAuth 2.0 (Authorization Code flow), read-scope only.

    Distinct from Google OAuth: this connects a candidate's *existing*
    GroundTruth account to their GitHub identity (`domains/student/github_oauth.py`)
    rather than authenticating into the app. `github_oauth_scopes` defaults to
    `read:user` (resolve the account) plus `public_repo` (list/read public
    repositories for the picker) — never a write or private-repo scope.
    """

    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:8000/api/v1/student/github/callback"
    github_oauth_scopes: str = "read:user public_repo"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)


@lru_cache
def get_github_oauth_settings() -> GitHubOAuthSettings:
    return GitHubOAuthSettings()


class VerificationSettings(BaseSettings):
    """Config for the third-party checks `src/jobs/tasks/verification.py` runs."""

    # Optional server-side PAT, used only when a candidate hasn't connected
    # GitHub via OAuth — raises the unauthenticated 60 req/hr GitHub rate
    # limit to the authenticated 5000 req/hr tier for account/repo checks.
    # Never required: without it, verification still works, just slower.
    github_api_token: str = ""
    verification_http_timeout_seconds: float = 15.0

    # Fixed-window caps per third-party host, shared by every worker process
    # via `clients/http.py::RateLimiter` (Redis-backed).
    github_rate_limit_per_minute: int = 30
    codeforces_rate_limit_per_minute: int = 20
    leetcode_rate_limit_per_minute: int = 20
    certificate_check_rate_limit_per_minute: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_verification_settings() -> VerificationSettings:
    return VerificationSettings()


class CelerySettings(BaseSettings):
    """Redis broker/result-backend URLs and worker retry policy.

    Retry values live here rather than as task decorator literals so the
    backoff envelope is tunable per environment without a code change.
    """

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Exponential backoff: delay = retry_backoff_base * 2**attempt, capped at
    # retry_backoff_max, with jitter applied by Celery to avoid thundering herds.
    job_max_retries: int = 3
    job_retry_backoff_base_seconds: int = 5
    job_retry_backoff_max_seconds: int = 600
    # Hard ceiling on a single task run; a task killed by this is retried.
    job_time_limit_seconds: int = 900
    job_soft_time_limit_seconds: int = 840

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_celery_settings() -> CelerySettings:
    return CelerySettings()


class RealtimeSettings(BaseSettings):
    """The WebSocket push layer (`src/realtime/`).

    `redis_url` finally has a reader: it has been in `.env`/`.env.example`
    since the first commit and nothing consumed it — Celery uses its own
    broker/result-backend URLs and the verification rate limiter borrows the
    result backend. A pub/sub fan-out is neither of those things, so it gets
    the general-purpose URL that was always meant for it.

    Note that Redis pub/sub channels are global to a server, not scoped to
    the numbered database in the URL, so which database this points at is
    irrelevant to delivery — it is set separately only so pub/sub traffic can
    be pointed at a different Redis instance from the job broker without a
    code change.
    """

    redis_url: str = "redis://localhost:6379/0"

    #: How long a freshly-accepted socket has to send its authentication
    #: frame before the server closes it. Short: the client sends the frame
    #: immediately on `onopen`, so anything slower is a client that is not
    #: going to authenticate, and an unauthenticated socket must not be able
    #: to hold a connection slot open indefinitely.
    realtime_auth_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_realtime_settings() -> RealtimeSettings:
    return RealtimeSettings()


class StorageSettings(BaseSettings):
    """S3-compatible object storage (MinIO in development, S3/R2 in production).

    One adapter covers both: MinIO speaks the S3 API, so only the endpoint and
    credentials differ between environments.
    """

    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_resume_bucket: str = "groundtruth-resumes"
    # Resumes are personal data: the bucket stays private and downloads are
    # served through short-lived presigned URLs rather than public objects.
    s3_presign_expiry_seconds: int = 300
    # Rejected before the body is read, so an oversized upload can't exhaust memory.
    resume_max_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.s3_access_key_id and self.s3_secret_access_key)


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()


class LLMSettings(BaseSettings):
    """Provider selection and per-call limits for the LLM service module.

    `default_llm_provider` selects which adapter `domains/ai/llm.py` builds;
    keys for every supported provider live here so swapping is a config change.
    """

    default_llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    # Google AI Studio (Gemini). Read by `providers/gemini_extractor.py`.
    google_api_key: str = ""

    llm_model: str = "claude-opus-5"
    llm_max_tokens: int = 16000
    # Scoped structured extraction — `medium` balances accuracy against the
    # latency and token spend of a job that runs on every resume upload.
    llm_effort: str = "medium"
    # Per-request wall clock. The worker's own time limit is deliberately
    # larger so a timeout surfaces as a typed LLM error, not a killed task.
    llm_timeout_seconds: float = 120.0
    # The SDK retries connection errors, 408/409/429 and 5xx on its own; the
    # Celery task retries the whole job on top of that.
    llm_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(
            {
                "anthropic": self.anthropic_api_key,
                "openai": self.openai_api_key,
                "groq": self.groq_api_key,
                "google": self.google_api_key,
            }.get(self.default_llm_provider)
        )

    @property
    def resume_extraction_model(self) -> str:
        """The model id for the *selected* provider.

        `llm_model` defaults to a Claude id, so pointing `DEFAULT_LLM_PROVIDER`
        at Google without also changing `LLM_MODEL` would send `claude-opus-5`
        to Gemini and 404. An explicit `LLM_MODEL` still wins — this only
        supplies a working default per provider.
        """
        if self.default_llm_provider == "google" and self.llm_model.startswith("claude"):
            return "gemini-3.6-flash"
        return self.llm_model


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


class EmbeddingSettings(BaseSettings):
    """Config for the matching engine's embedding calls
    (`domains/ai/providers/openai_embedder.py`).

    A separate provider from `LLMSettings.default_llm_provider` (Anthropic)
    on purpose: `text-embedding-3-small` is an OpenAI model with no
    Anthropic equivalent, so this is the one place the codebase talks to
    OpenAI rather than a configurable choice.
    """

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: float = 30.0
    embedding_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings()

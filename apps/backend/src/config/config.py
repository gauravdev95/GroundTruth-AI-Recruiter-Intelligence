"""Application settings, loaded from environment variables.

One settings class per concern, each cached via `lru_cache` so the
environment is only parsed once per process — same pattern as
`DatabaseSettings`.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: How far a set of weights may drift from 1.0 before it is rejected. Wide
#: enough to absorb the binary-float representation of decimal env values
#: (0.4 + 0.25 + 0.15 + 0.1 + 0.1 != 1.0 exactly in IEEE 754), tight enough
#: that a genuine typo — a weight entered as 0.5 instead of 0.05 — cannot pass.
_WEIGHT_SUM_TOLERANCE = 1e-6


def _validate_weight_set(weights: dict[str, float], *, label: str, env_prefix: str) -> None:
    """Reject a weight set that is not a probability distribution.

    Weights are operator-editable, and a score built from weights that do not
    sum to 1.0 is not on the 0-100 scale it is documented, stored
    (`Numeric(5,2)`), compared, and thresholded on. That failure is silent —
    every score simply comes out wrong together, so nothing looks broken — which
    is why this raises at settings-load time (process start) rather than being
    checked at the call site or left to a test.
    """
    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        detail = ", ".join(f"{env_prefix}{name.upper()}={value}" for name, value in weights.items())
        raise ValueError(
            f"{label} weights must sum to 1.0, got {total:.6f}. Configured: {detail}"
        )
    negative = [name for name, value in weights.items() if value < 0]
    if negative:
        raise ValueError(
            f"{label} weights must be non-negative; got a negative value for: {', '.join(negative)}"
        )


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
    # Platforms with no usable public API, checked by URL reachability only.
    hackerrank_rate_limit_per_minute: int = 20
    codechef_rate_limit_per_minute: int = 20
    atcoder_rate_limit_per_minute: int = 20
    geeksforgeeks_rate_limit_per_minute: int = 20
    # The `OTHER` platform points at a host this codebase has never seen, so it
    # gets its own conservative bucket rather than borrowing another
    # platform's — one candidate's unusual URL must not spend the budget a
    # named platform's checks depend on.
    other_platform_rate_limit_per_minute: int = 10
    certificate_check_rate_limit_per_minute: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_verification_settings() -> VerificationSettings:
    return VerificationSettings()


class MatchingSettings(BaseSettings):
    """The rank-fusion formula and cut for `domains/matching/`.

    Every term is operator-editable. The sum-to-1.0 invariant that makes
    `compute_match_score` produce a 0-100 number is enforced by
    `_validate_weight_set` at load time, so a bad weight set fails the process
    at start rather than silently rescaling every match in the system.

    The five terms are deliberately fewer than the eight signals the product
    brief lists, because several of those overlap and would double-count:

    * *project relevance* and *certificate relevance* are already inside
      `skill_evidence` — verified skills are **derived from** projects and
      certificates (`domains/verification/skills.py` is their only write site),
      so scoring them again counts the same evidence twice.
    * *experience match* is deliberately absent from the score entirely.
      `experiences` has no independent source of truth and can never reach
      `VERIFIED` (see `domains/student/models.py::Experience`), so weighting it
      would import unverified self-reports into a score whose whole premise is
      verified evidence. It constrains eligibility in the hard filter instead.
    """

    # Below this, a pair is absent from `match_results` entirely — not
    # low-ranked, not hidden at read time. Raising it therefore *prunes*
    # existing rows on the next recompute (except pairs an application
    # references, which `matching/service.py` preserves deliberately).
    match_threshold: float = 60.0

    #: Cosine similarity between the job and candidate profile vectors.
    #: The largest single term because role fit is what it actually captures;
    #: the evidence terms below establish that the fit is *real*, not that it
    #: exists.
    match_weight_semantic: float = 0.40
    #: Mean `candidate_skills.evidence_weight` across the job's required
    #: skills — repository- and certificate-derived evidence.
    match_weight_skill_evidence: float = 0.25
    #: The candidate's aggregate AI interview score (0-1).
    match_weight_interview: float = 0.15
    #: Competencies derived from verified coding profiles
    #: (`domains/verification/competencies.py`).
    match_weight_competency: float = 0.10
    #: Profile completeness. Smallest term: a complete profile is a weak
    #: signal next to evidence, and it was over-weighted at 0.20 when it was
    #: one of only three terms.
    match_weight_profile_strength: float = 0.10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def weights(self) -> dict[str, float]:
        """The formula as a name -> weight mapping.

        Keys match `compute_match_score`'s keyword arguments so the formula can
        be read, logged, and returned to the UI as one value rather than five
        attributes a caller has to know to fetch together.
        """
        return {
            "semantic": self.match_weight_semantic,
            "skill_evidence": self.match_weight_skill_evidence,
            "interview": self.match_weight_interview,
            "competency": self.match_weight_competency,
            "profile_strength": self.match_weight_profile_strength,
        }

    @model_validator(mode="after")
    def _check_weights(self) -> "MatchingSettings":
        _validate_weight_set(self.weights, label="Match", env_prefix="MATCH_WEIGHT_")
        if not 0.0 < self.match_threshold < 100.0:
            raise ValueError(
                f"MATCH_THRESHOLD must be between 0 and 100 (exclusive), got {self.match_threshold}. "
                "0 would persist every pair ever scored; 100 would persist none."
            )
        return self


@lru_cache
def get_matching_settings() -> MatchingSettings:
    return MatchingSettings()


class InterviewSettings(BaseSettings):
    """The live AI interview's scoring rubric and session limits.

    Weights are operator-editable and validated the same way as the match
    weights. Changing them does **not** rescore past interviews: every
    `interviews` row stores the `rubric_version` it was scored under, and an
    evidence report is written once and never edited (see
    `domains/interview/models.py`). A weight change therefore applies to
    interviews taken after it, which is the only honest option — a candidate
    cannot be retroactively re-judged against a rubric they never sat.
    """

    #: Bumped by hand when the *set* of dimensions changes, not when a weight
    #: moves. v1 was the original four-dimension rubric; v2 added
    #: `communication` and renamed the rest to the product vocabulary; v3 is
    #: the live interview's, which drops `repository_knowledge` as a separate
    #: axis — see `RUBRIC_V2_TO_V3` in `domains/interview/models.py`.
    interview_rubric_version: int = 3

    #: Is what the candidate said correct? The largest term, and back to v1's
    #: 0.40 now that it absorbs the claim-level checking the Verifier does
    #: continuously through the conversation.
    interview_weight_technical_accuracy: float = 0.40
    #: Do they understand their own code's logic, flow and design decisions?
    #: Carries what v2 split across `code_understanding` and
    #: `repository_knowledge`, which is why it rises from 0.25 without the
    #: code-grounded half of the rubric getting lighter: 0.25 here is measured
    #: against a whole conversation rather than one answer.
    interview_weight_code_understanding: float = 0.25
    #: Reasoning about trade-offs, alternatives and edge cases.
    interview_weight_problem_solving: float = 0.20
    #: Clarity of explanation. Smallest weight on purpose: it is the most
    #: subjective dimension for a model to judge and the least predictive of
    #: engineering ability. In a live interview it is also the dimension most
    #: at risk of scoring nerves rather than ability, which the Scorer's prompt
    #: forbids explicitly.
    interview_weight_communication: float = 0.15

    #: The session clock, in seconds. Copied onto each `interviews` row at
    #: creation so a change here cannot shorten an interview already underway.
    interview_time_limit_seconds: int = 600
    #: How much time must remain for the graph to start another question rather
    #: than heading for the close. Below this, wrapping up gracefully is worth
    #: more than one rushed answer.
    interview_wrapup_threshold_seconds: int = 90

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def rubric_weights(self) -> dict[str, float]:
        """Dimension name -> weight. Keys are the values stored in
        `interview_dimension_scores.dimension`, so a score row naming anything
        outside this mapping is a bug rather than a new dimension."""
        return {
            "technical_accuracy": self.interview_weight_technical_accuracy,
            "code_understanding": self.interview_weight_code_understanding,
            "problem_solving": self.interview_weight_problem_solving,
            "communication": self.interview_weight_communication,
        }

    @model_validator(mode="after")
    def _check_weights(self) -> "InterviewSettings":
        _validate_weight_set(self.rubric_weights, label="Interview rubric", env_prefix="INTERVIEW_WEIGHT_")
        if self.interview_time_limit_seconds <= self.interview_wrapup_threshold_seconds:
            raise ValueError(
                "INTERVIEW_TIME_LIMIT_SECONDS must exceed INTERVIEW_WRAPUP_THRESHOLD_SECONDS, "
                f"got {self.interview_time_limit_seconds} <= {self.interview_wrapup_threshold_seconds}. "
                "Otherwise every interview would open already out of time and wrap up "
                "without asking anything."
            )
        return self


@lru_cache
def get_interview_settings() -> InterviewSettings:
    return InterviewSettings()


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
    """Google Gemini credentials and per-call limits for `domains/ai/`.

    GroundTruth runs on one LLM provider. All four model-backed capabilities —
    resume extraction, interview question generation, answer evaluation, and
    job-requirement extraction — call Gemini through `domains/ai/llm.py`, so
    there is one key and one model id here rather than a provider-selection
    setting that can disagree with the keys actually present.

    Embeddings are outside this class entirely, and not because they use a
    second vendor: they run a local sentence-transformers model in-process and
    need no credential at all. See `EmbeddingSettings`.
    """

    #: Google AI Studio key. Required in practice — without it every capability
    #: above raises `LLMNotConfigured` (`domains/ai/llm.py`). Defaulted to empty
    #: rather than made mandatory so the API and the test suite still start on a
    #: machine with no key; only the LLM-backed paths fail, and they fail with a
    #: message naming this variable.
    google_api_key: str = ""

    #: The Gemini model every capability calls. Flash rather than Pro because
    #: all four prompts are scoped structured extraction against a fixed schema
    #: — the larger model's advantage is small there, and the latency is paid on
    #: paths a user is waiting on.
    llm_model: str = "gemini-3.6-flash"

    llm_max_tokens: int = 16000

    #: Per-request wall clock. The workers' Celery time limits are deliberately
    #: larger, so a slow provider surfaces as a typed `LLMTimeout` on the retry
    #: ladder instead of as a task killed mid-write.
    llm_timeout_seconds: float = 120.0

    #: Retries *within* a single request, applied by the SDK to 408/429/5xx.
    #: Kept small because the Celery task retries the whole job on top of this
    #: and the two budgets multiply: a job that has already spent two minutes on
    #: provider retries is better re-queued than held open.
    llm_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Whether the LLM-backed capabilities can run at all.

        One key, so this is the whole question — there is no "configured but
        not the provider you asked for" state to distinguish. Read by health
        checks and by `domains/ai/llm.py` before it builds any adapter.
        """
        return bool(self.google_api_key)


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


class EmbeddingSettings(BaseSettings):
    """Config for the matching engine's embeddings
    (`domains/ai/providers/local_embedder.py`).

    Nothing here is a credential: the matching engine embeds with an
    open-source sentence-transformers model running in the same process, so it
    is outside `LLMSettings` entirely — no key, no network call, and no
    per-request timeout or retry budget to tune.
    """

    #: Hugging Face model id, loaded by `sentence_transformers`.
    #:
    #: Editable in principle but *not* freely: the model's output dimension
    #: has to equal `domains/ai/embedding_constants.EMBEDDING_DIMENSIONS`,
    #: which is compiled into the pgvector column and its ANN index. A model
    #: of a different width needs a migration, and `LocalEmbedder` refuses to
    #: load one at start rather than failing every insert later.
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    #: "cpu", "cuda", "mps", … Empty means let sentence-transformers pick,
    #: which is CUDA when a GPU is visible and CPU otherwise. Worth pinning to
    #: "cpu" in containers that see a GPU they should not claim.
    embedding_device: str = ""
    #: Where the weights are cached. Empty means the Hugging Face default
    #: (`~/.cache/huggingface`). Set it to a mounted volume in Docker so the
    #: ~440 MB download happens once for the image rather than once per
    #: container start.
    embedding_cache_dir: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings()

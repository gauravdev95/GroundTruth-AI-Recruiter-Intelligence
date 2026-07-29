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


class EmailSettings(BaseSettings):
    """SMTP settings for transactional email. Left unset -> dev console fallback."""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@groundtruth.ai"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


@lru_cache
def get_email_settings() -> EmailSettings:
    return EmailSettings()


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

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def default_sqlite_database_url() -> str:
    """Stable path regardless of process cwd (avoids stray ./insightcase.db files)."""
    return f"sqlite:///{(_BACKEND_ROOT / 'insightcase.db').as_posix()}"


def _normalize_database_url(url: str) -> str:
    """Railway/Heroku often provide postgres:// without a SQLAlchemy driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    seed_demo_data: bool = False
    database_url: str = Field(default_factory=default_sqlite_database_url)
    redis_url: str = "redis://localhost:6379/0"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_refresh_secret_key: str = "dev-refresh-secret-change-in-production"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional regex for extra browser origins (Vercel preview URLs). In production, a safe
    # default for insightes-projects frontend previews is applied when this is unset.
    cors_origin_regex: str = ""
    frontend_url: str = "http://localhost:5173"
    support_contact_email: str = "support@insighte.com"
    support_office_address: str = "Insighte Childcare, Koramangala, Bangalore 560034"
    grievance_policy_url: str = "https://insighte.com/grievance-policy"
    policies_bot_url: str = ""
    support_phone: str = "+91 80 0000 0000"
    ticket_attachment_max_bytes: int = 5 * 1024 * 1024
    ticket_attachment_max_files: int = 3
    case_document_max_bytes: int = 5 * 1024 * 1024
    billing_ledger_drafts: bool = True
    # When false (pilot default), assignment acceptance timestamps are informational only.
    acceptance_gating_enabled: bool = False

    storage_provider: str = "local"
    storage_prefix: str = "insightcase"
    storage_environment: str = "development"
    max_upload_bytes: int = 10 * 1024 * 1024
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""

    email_provider: str = "smtp"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_email: str = "noreply@insighte.in"
    # When unset, billing/verification emails use smtp_from_email (required for single-sender ZeptoMail agents).
    smtp_from_billing_email: str = ""
    smtp_from_verification_email: str = ""
    smtp_from_name: str = "Insighte"
    smtp_tls: bool = True
    # Set true for port 465 (implicit SSL). When false, use SMTP_PORT with STARTTLS (587).
    smtp_ssl: bool = False
    admin_notification_emails: str = ""
    password_reset_expire_hours: int = 1
    password_reset_rate_limit_per_hour: int = 3
    email_invite_retry_delay_minutes: int = 15
    email_invite_max_attempts_24h: int = 3
    email_template_dedupe_minutes: int = 15
    email_recipient_max_per_day: int = 10
    email_admin_alert_on_failed_final: bool = True
    zeptomail_log_sync_enabled: bool = False
    zeptomail_log_sync_lookback_hours: int = 48
    zeptomail_api_key: str = ""
    zeptomail_mailagent_key: str = ""
    # IANA timezone for Google Calendar links in CM meeting invite emails (ctz=).
    meeting_invite_calendar_timezone: str = "Asia/Kolkata"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value

    @field_validator("smtp_user", "smtp_password", "smtp_host", mode="before")
    @classmethod
    def strip_smtp_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex_effective(self) -> str | None:
        explicit = (self.cors_origin_regex or "").strip()
        if explicit:
            return explicit
        if self.is_development:
            return None
        # Vercel production aliases (frontend-omega-eight-92.vercel.app) and git previews
        # (frontend-git-<branch>-insightes-projects.vercel.app). Explicit production URL
        # should still be listed in CORS_ORIGINS for invite/email link consistency.
        return r"https://frontend-[a-zA-Z0-9-]+\.vercel\.app"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local", "test")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def admin_notification_email_list(self) -> list[str]:
        return [e.strip() for e in self.admin_notification_emails.split(",") if e.strip()]

    def format_from_header(self, email: str) -> str:
        """Build RFC5322 From header for a bare sender address."""
        legacy = (self.smtp_from or "").strip()
        if legacy and email == (self.smtp_from_email or "").strip():
            if "<" in legacy:
                return legacy
            return legacy
        name = (self.smtp_from_name or "Insighte").strip()
        addr = (email or self.smtp_from_email or "noreply@insighte.in").strip()
        if "<" in addr:
            return addr
        return f"{name} <{addr}>"

    @property
    def smtp_from_header(self) -> str:
        """Default From header (general transactional)."""
        legacy = (self.smtp_from or "").strip()
        if legacy:
            return legacy
        return self.format_from_header(self.smtp_from_email)

    @property
    def storage_r2_endpoint(self) -> str:
        if self.r2_endpoint_url.strip():
            return self.r2_endpoint_url.strip().rstrip("/")
        account = self.r2_account_id.strip()
        if account:
            return f"https://{account}.r2.cloudflarestorage.com"
        return ""


settings = Settings()

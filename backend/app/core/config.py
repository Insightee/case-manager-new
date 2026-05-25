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
    database_url: str = Field(default_factory=default_sqlite_database_url)
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_refresh_secret_key: str = "dev-refresh-secret-change-in-production"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_url: str = "http://localhost:5173"
    support_contact_email: str = "support@insighte.com"
    support_office_address: str = "Insighte Childcare, Koramangala, Bangalore 560034"
    grievance_policy_url: str = "https://insighte.com/grievance-policy"
    policies_bot_url: str = ""
    support_phone: str = "+91 80 0000 0000"
    ticket_attachment_max_bytes: int = 5 * 1024 * 1024
    ticket_attachment_max_files: int = 3
    case_document_max_bytes: int = 15 * 1024 * 1024

    storage_provider: str = "local"
    storage_prefix: str = "insightcase"
    storage_environment: str = "development"
    max_upload_bytes: int = 10 * 1024 * 1024
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@insighte.com"
    smtp_tls: bool = True
    admin_notification_emails: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def admin_notification_email_list(self) -> list[str]:
        return [e.strip() for e in self.admin_notification_emails.split(",") if e.strip()]

    @property
    def storage_r2_endpoint(self) -> str:
        if self.r2_endpoint_url.strip():
            return self.r2_endpoint_url.strip().rstrip("/")
        account = self.r2_account_id.strip()
        if account:
            return f"https://{account}.r2.cloudflarestorage.com"
        return ""


settings = Settings()

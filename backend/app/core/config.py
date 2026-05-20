from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./insightcase.db"
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

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@insighte.com"
    smtp_tls: bool = True
    admin_notification_emails: str = ""

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


settings = Settings()

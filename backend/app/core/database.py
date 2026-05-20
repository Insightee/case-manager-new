from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
_engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": _connect_args}
if not settings.is_sqlite:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema_patches() -> None:
    """Apply additive SQLite columns when DB predates a migration (dev/test only)."""
    if not settings.is_sqlite or not settings.is_development:
        return
    insp = inspect(engine)
    if not insp.has_table("cases"):
        return
    cols = {c["name"] for c in insp.get_columns("cases")}
    if "client_billing_mode" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE cases ADD COLUMN client_billing_mode VARCHAR(32)"))

    if insp.has_table("invite_tokens"):
        inv_cols = {c["name"] for c in insp.get_columns("invite_tokens")}
        if "linked_child_id" not in inv_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invite_tokens ADD COLUMN linked_child_id INTEGER"))
        if "invite_metadata" not in inv_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invite_tokens ADD COLUMN invite_metadata TEXT"))

    if insp.has_table("therapist_slots"):
        slot_cols = {c["name"] for c in insp.get_columns("therapist_slots")}
        with engine.begin() as conn:
            if "approval_status" not in slot_cols:
                conn.execute(
                    text(
                        "ALTER TABLE therapist_slots ADD COLUMN approval_status VARCHAR(32) NOT NULL DEFAULT 'CONFIRMED'"
                    )
                )
            if "leave_block_leave_id" not in slot_cols:
                conn.execute(text("ALTER TABLE therapist_slots ADD COLUMN leave_block_leave_id INTEGER"))

    if insp.has_table("daily_logs"):
        log_cols = {c["name"] for c in insp.get_columns("daily_logs")}
        with engine.begin() as conn:
            if "parent_session_rating" not in log_cols:
                conn.execute(text("ALTER TABLE daily_logs ADD COLUMN parent_session_rating INTEGER"))
            if "parent_feedback" not in log_cols:
                conn.execute(text("ALTER TABLE daily_logs ADD COLUMN parent_feedback TEXT"))
            if "parent_feedback_at" not in log_cols:
                conn.execute(text("ALTER TABLE daily_logs ADD COLUMN parent_feedback_at DATETIME"))
            if "parent_feedback_public" not in log_cols:
                conn.execute(
                    text("ALTER TABLE daily_logs ADD COLUMN parent_feedback_public BOOLEAN NOT NULL DEFAULT 0")
                )

    if insp.has_table("support_tickets"):
        t_cols = {c["name"] for c in insp.get_columns("support_tickets")}
        with engine.begin() as conn:
            if "topic" not in t_cols:
                conn.execute(text("ALTER TABLE support_tickets ADD COLUMN topic VARCHAR(32) DEFAULT 'OTHER'"))
            if "escalation_level" not in t_cols:
                conn.execute(text("ALTER TABLE support_tickets ADD COLUMN escalation_level INTEGER DEFAULT 0"))
            if "parent_satisfaction_rating" not in t_cols:
                conn.execute(text("ALTER TABLE support_tickets ADD COLUMN parent_satisfaction_rating INTEGER"))
            if "parent_resolution_feedback" not in t_cols:
                conn.execute(text("ALTER TABLE support_tickets ADD COLUMN parent_resolution_feedback TEXT"))
            if "resolved_at" not in t_cols:
                conn.execute(text("ALTER TABLE support_tickets ADD COLUMN resolved_at DATETIME"))

    if not insp.has_table("ticket_attachments"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE ticket_attachments (
                        id INTEGER PRIMARY KEY,
                        ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),
                        message_id INTEGER REFERENCES ticket_messages(id),
                        file_name VARCHAR(255) NOT NULL,
                        file_path VARCHAR(512) NOT NULL,
                        mime_type VARCHAR(128) NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_attachments_ticket_id ON ticket_attachments (ticket_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_attachments_message_id ON ticket_attachments (message_id)"))

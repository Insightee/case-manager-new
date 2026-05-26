from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
_engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": _connect_args}
if not settings.is_sqlite:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_connect_pragmas(dbapi_connection, _connection_record) -> None:
    """WAL + busy_timeout reduce readonly/locked errors when seed runs alongside the API."""
    if not settings.is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema_patches() -> None:
    """Apply additive SQLite columns when DB predates a migration (local dev only).

    Production Postgres must use Alembic via ``scripts/migrate_production.py`` only.
    """
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

    if insp.has_table("users"):
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "avatar_path" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(512)"))
        if "is_view_only" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_view_only INTEGER NOT NULL DEFAULT 0"))
        if "module_access_grants" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN module_access_grants JSON"))
        if "feature_overrides" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN feature_overrides JSON"))

    if insp.has_table("therapist_profiles"):
        tp_cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
        with engine.begin() as conn:
            if "supervisor_user_id" not in tp_cols:
                conn.execute(text("ALTER TABLE therapist_profiles ADD COLUMN supervisor_user_id INTEGER"))
            if "mentor_user_id" not in tp_cols:
                conn.execute(text("ALTER TABLE therapist_profiles ADD COLUMN mentor_user_id INTEGER"))

    if not insp.has_table("service_categories"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE service_categories ("
                "  id VARCHAR(64) PRIMARY KEY,"
                "  label VARCHAR(255) NOT NULL,"
                "  description TEXT DEFAULT '',"
                "  is_active INTEGER NOT NULL DEFAULT 1,"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            _seed = [
                ("shadow", "Shadow support", 0),
                ("homecare", "Homecare", 1),
                ("occupational_therapy", "Occupational therapy", 2),
                ("speech_therapy", "Speech therapy", 3),
                ("special_educator", "Special educator", 4),
                ("behavior_therapy", "Behavior therapy", 5),
                ("play_therapy", "Play therapy", 6),
                ("customised_employment", "Customised employment", 7),
                ("subject_tutor", "Subject tutor", 8),
                ("sports", "Sports", 9),
                ("counselling", "Counselling", 10),
            ]
            for sid, label, order in _seed:
                conn.execute(text(
                    "INSERT OR IGNORE INTO service_categories (id, label, sort_order) VALUES (:id, :label, :order)"
                ), {"id": sid, "label": label, "order": order})

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

    if insp.has_table("ticket_messages"):
        tmsg_cols = {c["name"] for c in insp.get_columns("ticket_messages")}
        if "is_internal" not in tmsg_cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE ticket_messages ADD COLUMN is_internal BOOLEAN NOT NULL DEFAULT 0")
                )

    if insp.has_table("incidents"):
        inc_cols = {c["name"] for c in insp.get_columns("incidents")}
        with engine.begin() as conn:
            for col, ddl in (
                ("ticket_code", "VARCHAR(32)"),
                ("primary_category", "VARCHAR(64)"),
                ("subcategory", "VARCHAR(64)"),
                ("priority", "VARCHAR(16)"),
                ("service_type", "VARCHAR(32)"),
                ("incident_at", "DATETIME"),
                ("location", "VARCHAR(32)"),
                ("immediate_action", "TEXT"),
                ("child_safe", "VARCHAR(8)"),
                ("parent_informed", "VARCHAR(8)"),
                ("primary_owner_role", "VARCHAR(32)"),
                ("tagged_roles", "TEXT"),
                ("action_taken_note", "TEXT"),
                ("last_owner_activity_at", "DATETIME"),
                ("sla_reminder_sent_at", "DATETIME"),
                ("escalated_at", "DATETIME"),
            ):
                if col not in inc_cols:
                    conn.execute(text(f"ALTER TABLE incidents ADD COLUMN {col} {ddl}"))
            conn.execute(text("UPDATE incidents SET status = 'REPORTED' WHERE status = 'OPEN'"))
            conn.execute(text("UPDATE incidents SET status = 'IN_REVIEW' WHERE status = 'INVESTIGATING'"))
            conn.execute(text("UPDATE incidents SET status = 'ACTION_TAKEN' WHERE status = 'RESOLVED'"))
            conn.execute(
                text("UPDATE incidents SET ticket_code = 'INC-LEGACY-' || id WHERE ticket_code IS NULL")
            )

    if not insp.has_table("incident_attachments"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE incident_attachments (
                        id INTEGER PRIMARY KEY,
                        incident_id INTEGER NOT NULL REFERENCES incidents(id),
                        message_id INTEGER REFERENCES incident_messages(id),
                        file_name VARCHAR(255) NOT NULL,
                        file_path VARCHAR(512) NOT NULL,
                        mime_type VARCHAR(128) NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        note TEXT,
                        uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_incident_attachments_incident_id ON incident_attachments (incident_id)")
            )

    if not insp.has_table("observation_reports"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE observation_reports (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL REFERENCES cases(id),
                        therapist_user_id INTEGER NOT NULL REFERENCES users(id),
                        title VARCHAR(255) NOT NULL,
                        content TEXT,
                        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
                        visibility_status VARCHAR(32) NOT NULL DEFAULT 'INTERNAL_ONLY',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_observation_reports_case_id ON observation_reports (case_id)")
            )

    if insp.has_table("monthly_reports"):
        mr_cols = {c["name"] for c in insp.get_columns("monthly_reports")}
        with engine.begin() as conn:
            for col, ddl in (
                ("body_html", "TEXT"),
                ("plan_next_month", "TEXT"),
                ("category", "VARCHAR(32)"),
                ("sub_category", "VARCHAR(32)"),
                ("report_date", "DATE"),
            ):
                if col not in mr_cols:
                    conn.execute(text(f"ALTER TABLE monthly_reports ADD COLUMN {col} {ddl}"))

    if insp.has_table("observation_reports"):
        ob_cols = {c["name"] for c in insp.get_columns("observation_reports")}
        with engine.begin() as conn:
            for col, ddl in (
                ("body_html", "TEXT"),
                ("plan_next_month", "TEXT"),
                ("category", "VARCHAR(32)"),
                ("sub_category", "VARCHAR(32)"),
                ("report_date", "DATE"),
            ):
                if col not in ob_cols:
                    conn.execute(text(f"ALTER TABLE observation_reports ADD COLUMN {col} {ddl}"))

    if insp.has_table("audit_events"):
        audit_cols = {c["name"] for c in insp.get_columns("audit_events")}
        if "case_id" not in audit_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE audit_events ADD COLUMN case_id INTEGER"))

    _sqlite_portal_indexes(conn_ctx=engine)

    if not insp.has_table("report_images"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE report_images (
                        id INTEGER PRIMARY KEY,
                        report_type VARCHAR(32) NOT NULL,
                        report_id INTEGER NOT NULL,
                        file_name VARCHAR(255) NOT NULL,
                        file_path VARCHAR(512) NOT NULL,
                        uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_report_images_report "
                    "ON report_images (report_type, report_id)"
                )
            )

    if insp.has_table("report_images"):
        ri_cols = {c["name"] for c in insp.get_columns("report_images")}
        with engine.begin() as conn:
            for col, ddl in (
                ("storage_provider", "VARCHAR(16)"),
                ("storage_key", "VARCHAR(512)"),
                ("original_filename", "VARCHAR(255)"),
                ("mime_type", "VARCHAR(64)"),
                ("size_bytes", "INTEGER"),
            ):
                if col not in ri_cols:
                    conn.execute(text(f"ALTER TABLE report_images ADD COLUMN {col} {ddl}"))

    if insp.has_table("client_payments"):
        pay_cols = {c["name"] for c in insp.get_columns("client_payments")}
        with engine.begin() as conn:
            for col, ddl in (
                ("payment_status", "VARCHAR(32) NOT NULL DEFAULT 'CONFIRMED'"),
                ("submitted_by_user_id", "INTEGER"),
                ("proof_file_path", "VARCHAR(512)"),
                ("proof_file_name", "VARCHAR(255)"),
                ("confirmed_by_user_id", "INTEGER"),
                ("confirmed_at", "DATETIME"),
                ("rejection_note", "TEXT"),
            ):
                if col not in pay_cols:
                    conn.execute(text(f"ALTER TABLE client_payments ADD COLUMN {col} {ddl}"))

    if not insp.has_table("case_status_requests"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE case_status_requests (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL REFERENCES cases(id),
                        requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        from_status VARCHAR(32) NOT NULL,
                        to_status VARCHAR(32) NOT NULL,
                        reason TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
                        reviewed_by_user_id INTEGER REFERENCES users(id),
                        review_note TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_case_status_requests_case_id ON case_status_requests (case_id)")
            )

    if not insp.has_table("case_clinical_profiles"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE case_clinical_profiles (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
                        history TEXT,
                        diagnosis TEXT,
                        strengths TEXT,
                        interests TEXT,
                        goals_summary TEXT,
                        updated_by_user_id INTEGER REFERENCES users(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_case_clinical_profiles_case_id "
                    "ON case_clinical_profiles (case_id)"
                )
            )

    if not insp.has_table("observation_checklists"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE observation_checklists (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
                        therapist_user_id INTEGER NOT NULL REFERENCES users(id),
                        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
                        section_responses_json TEXT,
                        due_at DATE,
                        due_rule VARCHAR(64),
                        submitted_at DATETIME,
                        reviewed_by_user_id INTEGER REFERENCES users(id),
                        reviewer_comment TEXT,
                        reviewed_at DATETIME,
                        observation_report_id INTEGER REFERENCES observation_reports(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_observation_checklists_case_id "
                    "ON observation_checklists (case_id)"
                )
            )

    if not insp.has_table("iep_plans"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE iep_plans (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL REFERENCES cases(id),
                        version VARCHAR(32) NOT NULL DEFAULT 'v1',
                        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
                        sections_json TEXT,
                        visibility_status VARCHAR(32) NOT NULL DEFAULT 'INTERNAL_ONLY',
                        attachment_id INTEGER REFERENCES attachments(id),
                        created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        published_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_iep_plans_case_id ON iep_plans (case_id)")
            )

    if not insp.has_table("iep_plan_suggestions"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE iep_plan_suggestions (
                        id INTEGER PRIMARY KEY,
                        iep_plan_id INTEGER NOT NULL REFERENCES iep_plans(id),
                        author_user_id INTEGER NOT NULL REFERENCES users(id),
                        author_role VARCHAR(32) NOT NULL,
                        body TEXT NOT NULL,
                        resolved_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_iep_plan_suggestions_iep_plan_id "
                    "ON iep_plan_suggestions (iep_plan_id)"
                )
            )

    if insp.has_table("case_manager_meetings"):
        cols = {c["name"] for c in insp.get_columns("case_manager_meetings")}
        with engine.begin() as conn:
            if "meeting_url" not in cols:
                conn.execute(text("ALTER TABLE case_manager_meetings ADD COLUMN meeting_url VARCHAR(512)"))
            if "guest_emails_json" not in cols:
                conn.execute(text("ALTER TABLE case_manager_meetings ADD COLUMN guest_emails_json TEXT"))

    if insp.has_table("therapist_profiles"):
        tp_cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
        if "license_number" not in tp_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE therapist_profiles ADD COLUMN license_number VARCHAR(64)"))

    if insp.has_table("case_documents"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE case_documents SET status = 'CM_REVIEW' "
                    "WHERE status = 'SUPERVISOR_REVIEW'"
                )
            )
    if insp.has_table("case_document_workflow_events"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE case_document_workflow_events SET from_status = 'CM_REVIEW' "
                    "WHERE from_status = 'SUPERVISOR_REVIEW'"
                )
            )
            conn.execute(
                text(
                    "UPDATE case_document_workflow_events SET to_status = 'CM_REVIEW' "
                    "WHERE to_status = 'SUPERVISOR_REVIEW'"
                )
            )


def _sqlite_portal_indexes(conn_ctx=engine) -> None:
    """Idempotent composite indexes for portal query hardening (SQLite dev/test)."""
    if not settings.is_sqlite or not settings.is_development:
        return
    specs = [
        ("ix_audit_events_case_id_created_id", "audit_events", "case_id, created_at, id"),
        ("ix_audit_events_entity_type_id", "audit_events", "entity_type, entity_id"),
        ("ix_audit_events_created_id", "audit_events", "created_at, id"),
        ("ix_sessions_therapist_scheduled", "sessions", "therapist_user_id, scheduled_date"),
        ("ix_sessions_therapist_status", "sessions", "therapist_user_id, status"),
        ("ix_sessions_case_scheduled", "sessions", "case_id, scheduled_date"),
        ("ix_monthly_reports_therapist_status", "monthly_reports", "therapist_user_id, status"),
        ("ix_monthly_reports_case_month", "monthly_reports", "case_id, month"),
        ("ix_therapist_slots_therapist_date_status", "therapist_slots", "therapist_user_id, slot_date, status"),
        ("ix_therapist_slots_case_date_status", "therapist_slots", "case_id, slot_date, status"),
        ("ix_attachments_case_entity_type", "attachments", "case_id, entity_type"),
    ]
    insp = inspect(conn_ctx)
    with conn_ctx.begin() as conn:
        for name, table, cols in specs:
            if insp.has_table(table):
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))

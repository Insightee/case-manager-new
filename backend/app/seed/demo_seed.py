from __future__ import annotations

"""Run: python -m app.seed.demo_seed"""
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Base, SessionLocal, engine, ensure_sqlite_schema_patches
from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS, RoleName
from app.core.security import hash_password
from app.models import (
    Attachment,
    Case,
    CaseAssignment,
    Child,
    DailyLog,
    Invoice,
    MonthlyReport,
    ObservationReport,
    Notification,
    ParentBillingStatement,
    ParentGuardian,
    Permission,
    Role,
    TherapySession,
    User,
    parent_child_link,
)
from app.models.parent_billing import ParentBillingStatus
from app.models.client_billing import (
    CarePackage,
    CarePackageStatus,
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientInvoiceType,
    ClientPayment,
    PaymentMethod,
)
from app.models.assignment import CaseAssignmentStatus
from app.models.case import BillingType, CaseStatus, CompensationMode
from app.models.daily_log import LogApprovalStatus
from app.models.invoice import InvoiceStatus
from app.models.report import ReportStatus
from app.models.session import SessionMode, SessionStatus
from app.models.schedule_template import TherapistScheduleTemplate, default_template_config
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.models.leave import LeaveType, LeaveStatus, TherapistLeave
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.core.permissions import get_active_assignment
from app.services import case_service_service
from app.services import slot_calendar_service as cal
from app.models.incident import Incident, IncidentStatus
from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.visibility import VisibilityStatus
from app.models.service_category import ServiceCategory
from app.core.therapist_services import SERVICE_CATEGORIES


def seed_service_categories(db) -> None:
    """Ensure canonical clinical service lines exist for RBAC and case assignment."""
    for order, item in enumerate(SERVICE_CATEGORIES):
        sid = item["id"]
        label = item["label"]
        pm = [{"id": sid, "label": label}]
        cat = db.get(ServiceCategory, sid)
        if not cat:
            db.add(
                ServiceCategory(
                    id=sid,
                    label=label,
                    sort_order=order,
                    is_active=True,
                    access_group="Clinical",
                    product_modules=pm,
                )
            )
        else:
            cat.label = label
            cat.sort_order = order
            cat.is_active = True
            if not cat.product_modules:
                cat.product_modules = pm
    db.flush()


def seed_roles_permissions(db):
    for name in ALL_PERMISSIONS:
        if not db.scalars(select(Permission).where(Permission.name == name)).first():
            db.add(Permission(name=name))
    db.flush()
    perm_map = {p.name: p for p in db.scalars(select(Permission)).all()}
    for role_name, perms in ROLE_PERMISSIONS.items():
        role = db.scalars(select(Role).where(Role.name == role_name)).first()
        if not role:
            role = Role(name=role_name)
            db.add(role)
            db.flush()
        role.permissions = [perm_map[p] for p in perms if p in perm_map]


def get_or_create_user(db, email, password, full_name, role_name, **kwargs):
    """Create or refresh a demo user (password and active flag are always reset)."""
    email = email.lower().strip()
    role = db.scalars(select(Role).where(Role.name == role_name)).first()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user:
        user.password_hash = hash_password(password)
        user.full_name = full_name
        user.is_active = True
        if kwargs.get("region") is not None:
            user.region = kwargs["region"]
        if kwargs.get("module_assignments") is not None:
            user.module_assignments = kwargs["module_assignments"]
        if role:
            user.roles = [role]
        db.flush()
        return user
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
        region=kwargs.get("region", "south"),
        module_assignments=kwargs.get("module_assignments", []),
    )
    user.roles = [role] if role else []
    db.add(user)
    db.flush()
    return user


def ensure_active_case_assignment(
    db,
    *,
    case_id: int,
    therapist_user_id: int,
    assigned_by_user_id: int,
    start_date: date,
) -> None:
    """Idempotent: prod DBs may have ended or foreign assignments blocking book_slot."""
    case = db.get(Case, case_id)
    if not case:
        return
    default_service = case_service_service.ensure_default_case_service(db, case)
    if get_active_assignment(db, case_id, therapist_user_id):
        row = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.therapist_user_id == therapist_user_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if row and not row.case_service_id:
            row.case_service_id = default_service.id
        return
    row = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
        )
    ).first()
    if row:
        row.status = CaseAssignmentStatus.ACTIVE
        row.case_service_id = row.case_service_id or default_service.id
        if row.start_date is None:
            row.start_date = start_date
    else:
        db.add(
            CaseAssignment(
                case_id=case_id,
                case_service_id=default_service.id,
                therapist_user_id=therapist_user_id,
                assigned_by_user_id=assigned_by_user_id,
                start_date=start_date,
                status=CaseAssignmentStatus.ACTIVE,
            )
        )
    db.flush()


def run():
    ensure_sqlite_schema_patches()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_patches()
    db = SessionLocal()
    try:
        seed_roles_permissions(db)
        seed_service_categories(db)

        super_admin = get_or_create_user(db, "superadmin@demo.com", "demo123", "Super Admin", RoleName.SUPER_ADMIN.value)
        admin_user = get_or_create_user(
            db,
            "admin@demo.com",
            "demo123",
            "Programme Admin",
            RoleName.MODULE_ADMIN.value,
            module_assignments=["homecare"],
        )
        get_or_create_user(
            db,
            "moduleadmin@demo.com",
            "demo123",
            "Module Admin",
            RoleName.MODULE_ADMIN.value,
            module_assignments=["homecare", "shadow_support", "billing"],
        )
        case_mgr = get_or_create_user(
            db,
            "casemanager@demo.com",
            "demo123",
            "Case Manager Neha",
            RoleName.CASE_MANAGER.value,
            module_assignments=["homecare", "shadow_support"],
        )
        therapist = get_or_create_user(
            db,
            "therapist@demo.com",
            "demo123",
            "Therapist Neha",
            RoleName.THERAPIST.value,
            module_assignments=["homecare", "shadow_support"],
        )
        parent_user = get_or_create_user(db, "parent@demo.com", "demo123", "Parent Guardian", RoleName.PARENT.value)
        finance = get_or_create_user(
            db, "finance@demo.com", "demo123", "Finance User", RoleName.FINANCE.value, module_assignments=["billing"]
        )
        shadow_cm = get_or_create_user(
            db,
            "shadowcm@demo.com",
            "demo123",
            "Shadow Case Manager",
            RoleName.CASE_MANAGER.value,
            module_assignments=["shadow_support"],
        )
        view_only_cm = get_or_create_user(
            db,
            "viewonly@demo.com",
            "demo123",
            "CM View Only",
            RoleName.CASE_MANAGER.value,
            module_assignments=["homecare", "shadow_support"],
        )
        from app.core.rbac_access import sync_user_access_fields

        sync_user_access_fields(
            view_only_cm,
            role_names=[RoleName.CASE_MANAGER.value],
            module_assignments=["homecare", "shadow_support"],
            view_only=True,
        )
        sync_user_access_fields(
            shadow_cm,
            role_names=[RoleName.CASE_MANAGER.value],
            module_assignments=["shadow_support"],
            view_only=False,
        )
        sync_user_access_fields(
            admin_user,
            role_names=[RoleName.MODULE_ADMIN.value],
            module_assignments=["homecare"],
            view_only=False,
        )
        support_admin = get_or_create_user(
            db,
            "support@demo.com",
            "demo123",
            "Support Admin",
            RoleName.MODULE_ADMIN.value,
            module_assignments=["homecare", "billing"],
        )
        sync_user_access_fields(
            support_admin,
            role_names=[RoleName.MODULE_ADMIN.value],
            module_assignments=["homecare", "billing"],
            view_only=False,
        )
        hr_user = get_or_create_user(
            db, "hr@demo.com", "demo123", "HR Manager Priya", RoleName.HR.value, module_assignments=["people_admin", "hr_ops"]
        )
        sync_user_access_fields(
            hr_user,
            role_names=[RoleName.HR.value],
            org_capability_grants={
                "people_admin": {"enabled": True, "access": "write"},
                "hr_ops": {"enabled": True, "access": "write"},
            },
            view_only=False,
        )
        sync_user_access_fields(
            finance,
            role_names=[RoleName.FINANCE.value],
            org_capability_grants={"billing": {"enabled": True, "access": "write"}},
            view_only=False,
        )

        aarav = Child(first_name="Aarav", last_name="M.")
        ira = Child(first_name="Ira", last_name="K.")
        db.add_all([aarav, ira])
        db.flush()

        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent_user.id)).first()
        if not pg:
            pg = ParentGuardian(user_id=parent_user.id)
            db.add(pg)
            db.flush()
        for child in [aarav, ira]:
            if child not in pg.children:
                pg.children.append(child)

        case1 = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        if not case1:
            case1 = Case(
                case_code="IC-2026-041",
                child_id=aarav.id,
                service_type="Shadow Support",
                product_module="shadow_support",
                status=CaseStatus.ACTIVE,
                case_manager_user_id=case_mgr.id,
                region="south",
            )
            db.add(case1)
        case1.billing_type = BillingType.PER_SESSION
        case1.client_rate_per_session_inr = 1000
        case1.compensation_mode = CompensationMode.PERCENTAGE
        case1.pay_share_pct = 60
        case1.case_manager_user_id = shadow_cm.id

        case2 = db.scalars(select(Case).where(Case.case_code == "IC-2026-053")).first()
        if not case2:
            case2 = Case(
                case_code="IC-2026-053",
                child_id=ira.id,
                service_type="Homecare",
                product_module="homecare",
                status=CaseStatus.ACTIVE,
                case_manager_user_id=case_mgr.id,
                region="south",
            )
            db.add(case2)
        case2.billing_type = BillingType.PACKAGE
        case2.package_session_count = 20
        case2.package_amount_inr = 25000
        case2.compensation_mode = CompensationMode.PERCENTAGE
        case2.pay_share_pct = 60
        therapist.home_address_line1 = "42 Therapist Colony, 5th Block"
        therapist.home_city = "Bangalore"
        therapist.home_state = "Karnataka"
        therapist.home_pincode = "560034"
        therapist.home_landmark = "Near Koramangala BDA Complex"
        therapist.location = "Bangalore, 560034"
        case2.service_address_line1 = "18 Palm Grove Apartments"
        case2.service_address_line2 = "HSR Layout Sector 2"
        case2.service_city = "Bangalore"
        case2.service_state = "Karnataka"
        case2.service_pincode = "560102"
        case2.service_landmark = "Opposite BDA Complex"
        db.flush()

        tp = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)).first()
        if not tp:
            tp = TherapistProfile(
                user_id=therapist.id,
                display_name="Therapist Neha",
                short_bio="Experienced shadow and homecare therapist supporting children with diverse learning needs.",
                academic_qualifications="M.Sc. Psychology, B.Ed. Special Education",
                professional_certificates=["RCI Registered", "First Aid Certified"],
                services_offered=["shadow", "homecare", "behavior_therapy"],
                status=TherapistProfileStatus.APPROVED,
                employment_start_date=date(2019, 6, 1),
                leave_balance_year=date.today().year,
            )
            db.add(tp)
        elif tp.employment_start_date is None:
            tp.employment_start_date = date(2019, 6, 1)
            if tp.leave_balance_year is None:
                tp.leave_balance_year = date.today().year

        if not db.scalars(select(TherapistLeave).where(TherapistLeave.therapist_user_id == therapist.id)).first():
            db.add(
                TherapistLeave(
                    therapist_user_id=therapist.id,
                    leave_type=LeaveType.CASUAL,
                    start_date=date(2026, 5, 22),
                    end_date=date(2026, 5, 24),
                    reason="Family event",
                    status=LeaveStatus.APPROVED,
                )
            )
            db.add(
                TherapistLeave(
                    therapist_user_id=therapist.id,
                    leave_type=LeaveType.ANNUAL,
                    start_date=date(2026, 6, 15),
                    end_date=date(2026, 6, 16),
                    reason="Personal",
                    status=LeaveStatus.PENDING,
                )
            )

        ensure_active_case_assignment(
            db,
            case_id=case1.id,
            therapist_user_id=therapist.id,
            assigned_by_user_id=case_mgr.id,
            start_date=date(2026, 1, 1),
        )
        ensure_active_case_assignment(
            db,
            case_id=case2.id,
            therapist_user_id=therapist.id,
            assigned_by_user_id=case_mgr.id,
            start_date=date(2026, 2, 1),
        )

        def seed_session(case, day, hour=9, parent_visible=False):
            existing = db.scalars(
                select(TherapySession).where(
                    TherapySession.case_id == case.id,
                    TherapySession.scheduled_date == day,
                )
            ).first()
            if existing:
                if parent_visible:
                    log = db.scalars(select(DailyLog).where(DailyLog.session_id == existing.id)).first()
                    if log:
                        log.submitted_at = log.submitted_at or datetime.now(timezone.utc)
                        log.approval_status = LogApprovalStatus.APPROVED
                        log.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
                        log.parent_notes = log.parent_notes or "Great engagement during the session."
                        log.goals_addressed = log.goals_addressed or "Communication and social skills"
                        log.follow_ups = log.follow_ups or "Continue weekly sessions"
                return existing
            sess = TherapySession(
                case_id=case.id,
                therapist_user_id=therapist.id,
                scheduled_date=day,
                start_time=time(hour, 0),
                end_time=time(hour + 1, 0),
                mode=SessionMode.HOME,
                status=SessionStatus.COMPLETED,
            )
            db.add(sess)
            db.flush()
            vis = VisibilityStatus.APPROVED_FOR_PARENT if parent_visible else VisibilityStatus.INTERNAL_ONLY
            db.add(
                DailyLog(
                    session_id=sess.id,
                    attendance_status="PRESENT",
                    activities_done="Therapy activities and structured play",
                    goals_addressed="Communication and social skills" if parent_visible else None,
                    follow_ups="Continue weekly sessions" if parent_visible else None,
                    parent_notes="Great engagement during the session." if parent_visible else None,
                    observations="Approved for billing",
                    approval_status=LogApprovalStatus.APPROVED,
                    visibility_status=vis,
                    submitted_at=datetime.now(timezone.utc) if parent_visible else None,
                )
            )
            return sess

        seed_session(case1, date(2026, 4, 15), parent_visible=True)
        for d in [5, 8, 12, 15]:
            seed_session(case1, date(2026, 5, d), parent_visible=(d in (8, 15)))
        for d in [6, 13]:
            seed_session(case2, date(2026, 5, d), hour=10, parent_visible=True)

        def seed_scheduled(case, day, hour=14):
            existing = db.scalars(
                select(TherapySession).where(
                    TherapySession.case_id == case.id,
                    TherapySession.scheduled_date == day,
                )
            ).first()
            if existing:
                return
            db.add(
                TherapySession(
                    case_id=case.id,
                    therapist_user_id=therapist.id,
                    scheduled_date=day,
                    start_time=time(hour, 0),
                    end_time=time(hour + 1, 0),
                    mode=SessionMode.HOME,
                    status=SessionStatus.SCHEDULED,
                )
            )

        from datetime import timedelta

        today = date.today()
        seed_scheduled(case1, today, hour=10)
        seed_scheduled(case1, today + timedelta(days=2), hour=11)
        seed_scheduled(case2, today + timedelta(days=1), hour=15)

        completed_no_log = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case1.id,
                TherapySession.scheduled_date == today - timedelta(days=1),
            )
        ).first()
        if not completed_no_log:
            s = TherapySession(
                case_id=case1.id,
                therapist_user_id=therapist.id,
                scheduled_date=today - timedelta(days=1),
                start_time=time(9, 0),
                end_time=time(10, 0),
                mode=SessionMode.HOME,
                status=SessionStatus.COMPLETED,
            )
            db.add(s)

        pending_review_day = today - timedelta(days=2)
        pending_sess = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case1.id,
                TherapySession.scheduled_date == pending_review_day,
            )
        ).first()
        if not pending_sess:
            pending_sess = TherapySession(
                case_id=case1.id,
                therapist_user_id=therapist.id,
                scheduled_date=pending_review_day,
                start_time=time(11, 0),
                end_time=time(12, 0),
                mode=SessionMode.HOME,
                status=SessionStatus.COMPLETED,
            )
            db.add(pending_sess)
            db.flush()
        pending_log = db.scalars(select(DailyLog).where(DailyLog.session_id == pending_sess.id)).first()
        if not pending_log:
            db.add(
                DailyLog(
                    session_id=pending_sess.id,
                    attendance_status="PRESENT",
                    activities_done="Sensory integration activities",
                    session_notes="Internal: good focus today",
                    goals_addressed="Fine motor skills",
                    observations="Internal observation notes",
                    follow_ups="Practice at home",
                    parent_notes="Aarav participated well in today's session.",
                    submitted_at=datetime.now(timezone.utc),
                    approval_status=LogApprovalStatus.PENDING,
                    visibility_status=VisibilityStatus.INTERNAL_ONLY,
                )
            )

        if not db.scalars(select(TherapistScheduleTemplate).where(TherapistScheduleTemplate.therapist_user_id == therapist.id)).first():
            tpl = TherapistScheduleTemplate(therapist_user_id=therapist.id)
            tpl.set_config(default_template_config())
            db.add(tpl)
            db.flush()
        cal.materialize_range(db, therapist.id, date(2026, 6, 1), date(2026, 6, 30))
        sample_slot = db.scalars(
            select(TherapistSlot).where(
                TherapistSlot.therapist_user_id == therapist.id,
                TherapistSlot.status == SlotStatus.AVAILABLE,
            )
        ).first()
        if sample_slot:
            try:
                cal.book_slot(db, sample_slot.id, case1.id, therapist.id, BookingSource.THERAPIST)
            except ValueError:
                pass  # idempotent re-seed: slot booked or assignment already changed

        if not db.scalars(select(MonthlyReport).where(MonthlyReport.case_id == case1.id)).first():
            db.add(
                MonthlyReport(
                    case_id=case1.id,
                    therapist_user_id=therapist.id,
                    month="Apr 2026",
                    status=ReportStatus.UNDER_REVIEW,
                    summary="Strong progress on communication goals",
                    visibility_status=VisibilityStatus.INTERNAL_ONLY,
                )
            )
            db.add(
                MonthlyReport(
                    case_id=case1.id,
                    therapist_user_id=therapist.id,
                    month="Mar 2026",
                    status=ReportStatus.PUBLISHED,
                    summary="Published report for parent",
                    visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
                )
            )

        if not db.scalars(select(ObservationReport).where(ObservationReport.case_id == case1.id)).first():
            db.add(
                ObservationReport(
                    case_id=case1.id,
                    therapist_user_id=therapist.id,
                    title="Classroom shadow observation",
                    content="Student engaged well during group activity; minor sensory breaks needed.",
                    status=ReportStatus.UNDER_REVIEW,
                    visibility_status=VisibilityStatus.INTERNAL_ONLY,
                )
            )
            db.add(
                ObservationReport(
                    case_id=case1.id,
                    therapist_user_id=therapist.id,
                    title="Home visit observation",
                    content="Parent implemented strategies from last session.",
                    status=ReportStatus.PUBLISHED,
                    visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
                )
            )

        if not db.scalars(select(Invoice).where(Invoice.therapist_user_id == therapist.id)).first():
            db.add(
                Invoice(
                    therapist_user_id=therapist.id,
                    month="Apr 2026",
                    amount_inr=42500,
                    sessions_count=32,
                    status=InvoiceStatus.IN_REVIEW,
                )
            )

        if not db.scalars(
            select(Attachment).where(Attachment.case_id == case1.id, Attachment.entity_type == "iep")
        ).first():
            import os

            iep_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "iep")
            os.makedirs(iep_dir, exist_ok=True)
            iep_path = os.path.join(iep_dir, f"iep_case_{case1.id}.txt")
            if not os.path.isfile(iep_path):
                with open(iep_path, "w", encoding="utf-8") as f:
                    f.write("Demo IEP document for parent acknowledgement flow.")
            db.add(
                Attachment(
                    case_id=case1.id,
                    entity_type="iep",
                    file_name="IEP_Spring_2026.pdf",
                    file_path=iep_path,
                    version="Spring 2026",
                    visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
                    uploaded_by_user_id=case_mgr.id,
                )
            )

        if not db.scalars(select(Notification).where(Notification.user_id == parent_user.id)).first():
            db.add(
                Notification(
                    user_id=parent_user.id,
                    title="Monthly report published",
                    body="The March 2026 report for Aarav is now available in your portal.",
                    entity_type="monthly_report",
                    is_read=False,
                )
            )
            db.add(
                Notification(
                    user_id=parent_user.id,
                    title="Session update approved",
                    body="A new session update has been shared for your review.",
                    is_read=False,
                )
            )

        if not db.scalars(
            select(ParentBillingStatement).where(ParentBillingStatement.parent_user_id == parent_user.id)
        ).first():
            db.add(
                ParentBillingStatement(
                    parent_user_id=parent_user.id,
                    case_id=case1.id,
                    month="Apr 2026",
                    amount_inr=12000,
                    status=ParentBillingStatus.DUE,
                    detail="Homecare package — April 2026",
                )
            )
            db.add(
                ParentBillingStatement(
                    parent_user_id=parent_user.id,
                    case_id=case2.id,
                    month="Mar 2026",
                    amount_inr=8500,
                    status=ParentBillingStatus.PAID,
                    detail="Shadow support — March 2026",
                )
            )

        if not db.scalars(select(ClientInvoice).limit(1)).first():
            inv_may = ClientInvoice(
                invoice_number="INV-2026-0201",
                parent_user_id=parent_user.id,
                case_id=case1.id,
                invoice_type=ClientInvoiceType.POSTPAID,
                status=ClientInvoiceStatus.GENERATED,
                billing_month="2026-05",
                service_type=case1.service_type,
                product_module=case1.product_module,
                due_date=date(2026, 5, 10),
                subtotal_inr=4800,
                tax_inr=0,
                discount_inr=0,
                package_deduction_inr=0,
                adjustment_inr=0,
                total_inr=4800,
                amount_paid_inr=0,
                notes="Postpaid monthly invoice for homecare sessions in May 2026.",
                sent_at=None,
            )
            db.add(inv_may)
            db.flush()
            db.add_all(
                [
                    ClientInvoiceLine(
                        client_invoice_id=inv_may.id,
                        session_date=date(2026, 5, 5),
                        therapist_name=therapist.full_name,
                        service_label=case1.service_type,
                        session_status="Completed",
                        amount_inr=1200,
                        package_deducted=False,
                        parent_summary="Structured play and communication activities",
                        sort_order=1,
                    ),
                    ClientInvoiceLine(
                        client_invoice_id=inv_may.id,
                        session_date=date(2026, 5, 8),
                        therapist_name=therapist.full_name,
                        service_label=case1.service_type,
                        session_status="Completed",
                        amount_inr=1200,
                        package_deducted=False,
                        parent_summary="Goals: communication and social skills",
                        sort_order=2,
                    ),
                    ClientInvoiceLine(
                        client_invoice_id=inv_may.id,
                        session_date=date(2026, 5, 12),
                        therapist_name=therapist.full_name,
                        service_label=case1.service_type,
                        session_status="Client Absent",
                        amount_inr=0,
                        package_deducted=False,
                        parent_summary="Family informed in advance — no charge",
                        sort_order=3,
                    ),
                    ClientInvoiceLine(
                        client_invoice_id=inv_may.id,
                        session_date=date(2026, 5, 15),
                        therapist_name=therapist.full_name,
                        service_label=case1.service_type,
                        session_status="Completed",
                        amount_inr=2400,
                        package_deducted=False,
                        parent_summary="Extended session — progress on IEP goals",
                        sort_order=4,
                    ),
                ]
            )
            try:
                from app.services import client_billing_service as _client_billing

                _client_billing.notify_parent_invoice_issued(db, inv_may.id, resend=False)
            except Exception:
                pass
            inv_mar = ClientInvoice(
                invoice_number="INV-2026-0103",
                parent_user_id=parent_user.id,
                case_id=case2.id,
                invoice_type=ClientInvoiceType.PREPAID,
                status=ClientInvoiceStatus.PAID,
                billing_month="2026-03",
                service_type=case2.service_type,
                product_module=case2.product_module,
                due_date=date(2026, 3, 31),
                subtotal_inr=8500,
                tax_inr=0,
                discount_inr=500,
                package_deduction_inr=0,
                adjustment_inr=0,
                total_inr=8000,
                amount_paid_inr=8000,
                notes="Prepaid shadow support package — March usage.",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(inv_mar)
            db.flush()
            db.add_all(
                [
                    ClientInvoiceLine(
                        client_invoice_id=inv_mar.id,
                        session_date=date(2026, 3, 6),
                        therapist_name=therapist.full_name,
                        service_label=case2.service_type,
                        session_status="Completed",
                        amount_inr=4000,
                        package_deducted=True,
                        parent_summary="Shadow support at school",
                        sort_order=1,
                    ),
                    ClientInvoiceLine(
                        client_invoice_id=inv_mar.id,
                        session_date=date(2026, 3, 13),
                        therapist_name=therapist.full_name,
                        service_label=case2.service_type,
                        session_status="Completed",
                        amount_inr=4000,
                        package_deducted=True,
                        parent_summary="Classroom inclusion support",
                        sort_order=2,
                    ),
                ]
            )
            db.add(
                ClientPayment(
                    client_invoice_id=inv_mar.id,
                    amount_inr=8000,
                    method=PaymentMethod.UPI,
                    reference="UPI-8839201",
                    recorded_by_user_id=finance.id if finance else case_mgr.id,
                )
            )
            db.add(
                CarePackage(
                    case_id=case1.id,
                    parent_user_id=parent_user.id,
                    name="Homecare 20 Session Pack",
                    total_sessions=20,
                    used_sessions=8,
                    validity_end=date(2026, 6, 30),
                    service_label=case1.service_type,
                    status=CarePackageStatus.ACTIVE,
                )
            )
            db.add(
                CarePackage(
                    case_id=case2.id,
                    parent_user_id=parent_user.id,
                    name="Shadow Support 12 Session Pack",
                    total_sessions=12,
                    used_sessions=10,
                    validity_end=date(2026, 5, 31),
                    service_label=case2.service_type,
                    status=CarePackageStatus.ACTIVE,
                )
            )
            db.add(
                Notification(
                    user_id=parent_user.id,
                    title="May invoice generated",
                    body="Your May invoice for Aarav has been generated. ₹4,800 due by 10 Jun.",
                    is_read=False,
                    entity_type="client_invoice",
                    entity_id=inv_may.id,
                )
            )

        if not db.scalars(select(CaseManagerMeeting).limit(1)).first():
            db.add(
                CaseManagerMeeting(
                    case_manager_user_id=case_mgr.id,
                    case_id=case1.id,
                    parent_user_id=parent_user.id,
                    scheduled_date=date(2026, 5, 28),
                    scheduled_time=time(10, 0),
                    duration_minutes=45,
                    meeting_type=MeetingType.CLIENT_ONLY,
                    title="Monthly check-in — Aarav",
                    status=MeetingStatus.SCHEDULED,
                )
            )
            db.add(
                CaseManagerMeeting(
                    case_manager_user_id=case_mgr.id,
                    case_id=case1.id,
                    therapist_user_id=therapist.id,
                    scheduled_date=date(2026, 6, 5),
                    scheduled_time=time(14, 30),
                    duration_minutes=30,
                    meeting_type=MeetingType.SUPERVISION,
                    title="Supervision — shadow support case",
                    status=MeetingStatus.SCHEDULED,
                )
            )

        if not db.scalars(
            select(SupportTicket).where(SupportTicket.subject == "Demo finance billing query")
        ).first():
            db.add(
                SupportTicket(
                    raised_by_user_id=finance.id,
                    subject="Demo finance billing query",
                    body="Seeded ticket for finance support hub history.",
                    category=TicketCategory.FINANCE,
                    status=TicketStatus.OPEN,
                    product_module=None,
                )
            )
        if not db.scalars(
            select(SupportTicket).where(SupportTicket.subject == "Demo HR leave policy question")
        ).first():
            db.add(
                SupportTicket(
                    raised_by_user_id=hr_user.id,
                    subject="Demo HR leave policy question",
                    body="Seeded ticket for HR support hub history.",
                    category=TicketCategory.HR,
                    status=TicketStatus.OPEN,
                    product_module=None,
                )
            )

        if not db.scalars(select(Incident).limit(1)).first():
            db.add(
                Incident(
                    case_id=case1.id,
                    reported_by_user_id=therapist.id,
                    title="Minor equipment concern",
                    description="Therapy mat showed wear during home visit; replacement requested.",
                    is_sensitive=False,
                    ticket_code="INC-2026-00001",
                    primary_category="SESSION_CLASSROOM_PROGRAM",
                    subcategory="session_disrupted",
                    priority="NORMAL",
                    status=IncidentStatus.REPORTED,
                )
            )
            db.add(
                Incident(
                    case_id=case2.id,
                    reported_by_user_id=case_mgr.id,
                    title="Scheduling conflict noted",
                    description="Parent requested reschedule due to school event.",
                    is_sensitive=False,
                    ticket_code="INC-2026-00002",
                    primary_category="PARENT_SCHOOL_COMMUNICATION",
                    subcategory="communication_delay",
                    priority="NORMAL",
                    status=IncidentStatus.IN_REVIEW,
                )
            )

        if not db.scalars(
            select(Incident).where(Incident.ticket_code == "INC-2026-00003")
        ).first():
            db.add(
                Incident(
                    case_id=case2.id,
                    reported_by_user_id=hr_user.id,
                    title="HR workplace concern (demo)",
                    description="Seeded incident reported by HR for own-scope history.",
                    is_sensitive=False,
                    ticket_code="INC-2026-00003",
                    primary_category="OTHER",
                    subcategory="other",
                    priority="NORMAL",
                    status=IncidentStatus.REPORTED,
                )
            )

        from app.seed.product_billing_rules_seed import seed_product_billing_rules

        seed_product_billing_rules(db)

        _LEGACY_ROLE_NAMES = frozenset(
            {RoleName.ADMIN.value, RoleName.VIEWER.value, RoleName.SUPERVISOR.value}
        )
        for u in db.scalars(select(User).options(selectinload(User.roles))).all():
            names = {r.name for r in (u.roles or [])}
            if names and names <= _LEGACY_ROLE_NAMES:
                u.is_active = False
        for legacy_email in ("supervisor@demo.com", "viewer@demo.com"):
            legacy = db.scalars(select(User).where(User.email == legacy_email)).first()
            if legacy:
                legacy.is_active = False

        db.commit()
        print("Demo seed completed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

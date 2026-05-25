from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assignments,
    attachments,
    auth,
    notifications,
    cases,
    cm_meetings,
    daily_logs,
    hr,
    incidents,
    invoices,
    leave,
    parent,
    reports,
    sessions,
    booking,
    slots,
    scheduling,
    tickets,
    support,
    therapist_profile,
    therapist_portal,
    geocode,
    files,
    client_billing,
    case_documents,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(notifications.router)
api_router.include_router(cm_meetings.router)
api_router.include_router(cases.router)
api_router.include_router(assignments.router)
api_router.include_router(sessions.router)
api_router.include_router(daily_logs.router)
api_router.include_router(reports.router)
api_router.include_router(invoices.router)
api_router.include_router(admin.router)
api_router.include_router(parent.router)
api_router.include_router(client_billing.parent_router)
api_router.include_router(client_billing.admin_router)
api_router.include_router(tickets.router)
api_router.include_router(support.router)
api_router.include_router(attachments.router)
api_router.include_router(incidents.router)
api_router.include_router(leave.router)
api_router.include_router(slots.router)
api_router.include_router(scheduling.router)
api_router.include_router(booking.router)
api_router.include_router(hr.router)
api_router.include_router(therapist_profile.router)
api_router.include_router(therapist_portal.router)
api_router.include_router(geocode.router)
api_router.include_router(files.router)
api_router.include_router(case_documents.router)
api_router.include_router(case_documents.documents_router)

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assignments,
    attachments,
    auth,
    cases,
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
    tickets,
    therapist_profile,
    geocode,
    files,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(assignments.router)
api_router.include_router(sessions.router)
api_router.include_router(daily_logs.router)
api_router.include_router(reports.router)
api_router.include_router(invoices.router)
api_router.include_router(admin.router)
api_router.include_router(parent.router)
api_router.include_router(tickets.router)
api_router.include_router(attachments.router)
api_router.include_router(incidents.router)
api_router.include_router(leave.router)
api_router.include_router(slots.router)
api_router.include_router(booking.router)
api_router.include_router(hr.router)
api_router.include_router(therapist_profile.router)
api_router.include_router(geocode.router)
api_router.include_router(files.router)

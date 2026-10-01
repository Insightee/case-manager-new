from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.parent_notification_preferences import apply_parent_email_preferences


def test_appointment_email_respects_opt_out():
    from app.services.appointment_notification_service import notify_parents_therapist_booked

    user = SimpleNamespace(
        id=1,
        email="parent@example.com",
        notification_preferences={},
        role_names=["PARENT"],
    )
    apply_parent_email_preferences(user, {"appointments": False})

    slot = SimpleNamespace(
        id=99,
        case_id=10,
        slot_date=SimpleNamespace(isoformat=lambda: "2026-09-01"),
        start_time=SimpleNamespace(strftime=lambda _: "08:00"),
    )
    case = SimpleNamespace(child=SimpleNamespace(full_name="M. Arjun"))
    sent: list[str] = []

    class FakeDb:
        def get(self, model, pk):
            if pk == 10:
                return case
            return user

    with patch(
        "app.services.appointment_notification_service._parent_users_for_case",
        return_value=[user],
    ), patch(
        "app.services.appointment_notification_service.notification_service.create_notification",
    ), patch(
        "app.services.appointment_notification_service.email_service.booking_confirmed_email",
        side_effect=lambda **kw: sent.append(kw["to"]),
    ):
        notify_parents_therapist_booked(FakeDb(), slot, therapist_name="Umme Asra.N")

    assert sent == []

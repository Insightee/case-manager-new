from datetime import date, datetime, timezone

from app.services.support_ticket_question_groups import QUESTION_GROUPS, classify_question
from app.services.support_ticket_report_service import age_in_days, count_roles, median_hours, module_bucket


def test_question_groups_cover_the_report_taxonomy():
    labels = [label for _key, label in QUESTION_GROUPS]
    assert labels == [
        "Pay mismatch",
        "Leave",
        "Child absence",
        "Deduction",
        "Invoice",
        "Extra day or hours",
        "Session log",
        "Schedule",
        "Holiday",
        "Training or certificate",
        "Session dispute",
        "Login or app not working",
        "Reports",
        "Case assignment",
        "Clinical or incident",
        "Resignation",
        "Reimbursement",
        "Other",
    ]


def test_classify_repeating_questions_from_subject_and_opening_body():
    samples = [
        ("Salary discrepancy", "", "pay_mismatch"),
        ("", "payment has not been credited", "pay_mismatch"),
        ("Query regarding approved leave", "", "leave"),
        ("Could not mark child absence", "", "child_absence"),
        ("", "absence not reflected", "child_absence"),
        ("Incorrect leave deduction", "", "deduction"),
        ("Could not generate invoice", "", "invoice"),
        ("Incorrect name on invoice", "", "invoice"),
        ("Extra Saturday", "pay for an extra day", "extra_day_or_hours"),
        ("Unable to see the session logs", "", "session_log"),
        ("Reschedule time", "", "schedule"),
        ("Not able to mark school holiday", "", "holiday"),
        ("Request for an experience certificate", "", "training_or_certificate"),
        ("Dispute session on 12 May", "", "session_dispute"),
        ("Login", "app not working", "login_or_app"),
        ("Monthly report is missing", "", "reports"),
        ("Wrong case assignment", "", "case_assignment"),
        ("Incident at the session", "a child was hurt", "clinical_or_incident"),
        ("Resignation notice", "", "resignation"),
        ("Travel reimbursement", "", "reimbursement"),
        ("Hello there", "general question", "other"),
    ]
    for subject, body, expected in samples:
        assert classify_question(subject, body) == expected, subject or body


def test_role_counts_include_each_role_for_the_same_person():
    assert count_roles([["THERAPIST", "HR"], ["THERAPIST"], []]) == {
        "THERAPIST": 2,
        "HR": 1,
        "NO_ROLE": 1,
    }


def test_median_hours_and_ist_age():
    assert median_hours([]) is None
    assert median_hours([10, 30]) == 20.0
    assert median_hours([67]) == 67.0
    opened = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)  # 2026-09-25 00:00 IST
    assert age_in_days(opened, date(2026, 10, 1)) == 6


def test_module_buckets():
    assert module_bucket(None) == "none"
    assert module_bucket("  ") == "none"
    assert module_bucket("shadow") == "shadow_support"
    assert module_bucket("Home Care") == "homecare"
    assert module_bucket("B2B") == "b2b"

"""Place each support ticket in one repeating-question group.

Groups are approximate. Matching uses the subject and the opening body only.
The first matching pattern wins. Tickets that match nothing land in Other.
"""
from __future__ import annotations

import re

# Display order for the report. Matching order is separate and more specific first.
QUESTION_GROUPS: tuple[tuple[str, str], ...] = (
    ("pay_mismatch", "Pay mismatch"),
    ("leave", "Leave"),
    ("child_absence", "Child absence"),
    ("deduction", "Deduction"),
    ("invoice", "Invoice"),
    ("extra_day_or_hours", "Extra day or hours"),
    ("session_log", "Session log"),
    ("schedule", "Schedule"),
    ("holiday", "Holiday"),
    ("training_or_certificate", "Training or certificate"),
    ("session_dispute", "Session dispute"),
    ("login_or_app", "Login or app not working"),
    ("reports", "Reports"),
    ("case_assignment", "Case assignment"),
    ("clinical_or_incident", "Clinical or incident"),
    ("resignation", "Resignation"),
    ("reimbursement", "Reimbursement"),
    ("other", "Other"),
)

QUESTION_GROUP_LABELS: dict[str, str] = dict(QUESTION_GROUPS)

# More specific overlaps are listed before broader words such as pay or leave.
_MATCH_ORDER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("reimbursement", re.compile(r"\breimburs", re.IGNORECASE)),
    ("resignation", re.compile(r"\bresign|last working day|\bnotice period\b", re.IGNORECASE)),
    (
        "clinical_or_incident",
        re.compile(
            r"\bincident\b|\binjur|\bbehaviou?r\b|\babuse\b|\bsafeguard|\bchild protection\b|\bposh\b|\bcpp\b|\bclinical\b",
            re.IGNORECASE,
        ),
    ),
    (
        "session_dispute",
        re.compile(r"session dispute|disput(?:e|ed|ing)\s+(?:the\s+|a\s+)?session", re.IGNORECASE),
    ),
    (
        "child_absence",
        re.compile(
            r"child absence|client absent|child (?:was |is )?absent|"
            r"mark(?:ing)?\s+(?:a |the )?(?:child )?absence|absence not|"
            r"(?:could not|cannot|unable to) mark[\s\S]{0,40}absence",
            re.IGNORECASE,
        ),
    ),
    ("deduction", re.compile(r"\bdeduct", re.IGNORECASE)),
    (
        "extra_day_or_hours",
        re.compile(r"extra hours?|extra days?|extra saturday|additional hours?", re.IGNORECASE),
    ),
    ("invoice", re.compile(r"\binvoices?\b", re.IGNORECASE)),
    (
        "pay_mismatch",
        re.compile(
            r"\bsalary|\bpayouts?\b|\bpayments?\b|\bremuneration\b|not credited|pay mismatch|\bdiscrepanc",
            re.IGNORECASE,
        ),
    ),
    ("leave", re.compile(r"\bleaves?\b", re.IGNORECASE)),
    ("session_log", re.compile(r"session logs?|clock[\s-]?out", re.IGNORECASE)),
    ("schedule", re.compile(r"\breschedul|\bschedul", re.IGNORECASE)),
    ("holiday", re.compile(r"\bholidays?\b", re.IGNORECASE)),
    (
        "training_or_certificate",
        re.compile(r"\bcertificates?\b|\bexperience letter\b|\btrainings?\b", re.IGNORECASE),
    ),
    (
        "login_or_app",
        re.compile(
            r"\blog[\s-]?in\b|not working|isn'?t working|app not|cannot access|can'?t access|"
            r"unable to (?:log|access|open)",
            re.IGNORECASE,
        ),
    ),
    ("reports", re.compile(r"\breports?\b|\bdocuments?\b", re.IGNORECASE)),
    ("case_assignment", re.compile(r"case assignment|wrong case|case assign", re.IGNORECASE)),
)


def classify_question(subject: str | None, opening_body: str | None) -> str:
    text = f"{subject or ''} {opening_body or ''}"
    for key, pattern in _MATCH_ORDER:
        if pattern.search(text):
            return key
    return "other"

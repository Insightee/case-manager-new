"""Deterministic therapist listing quality score. Layer 1 — no LLM."""
from __future__ import annotations

import re
from typing import Any

BIO_MIN_WORDS = 40
BIO_MAX_CHARS = 800
PINCODE_RE = re.compile(r"^\d{6}$")
YEAR_MIN = 1950
YEAR_MAX = 2035

QUALITY_WEIGHTS = {
    "avatar": 20,
    "home_address": 10,
    "pincode": 10,
    "phone": 10,
    "email": 5,
    "short_bio": 20,
    "degree": 15,
    "services_offered": 10,
}

REMINDERS = {
    "avatar": "Your profile photo still needs to be added so families recognise you.",
    "home_address": "Add your street and city so we have a complete address.",
    "pincode": "Add your 6-digit pincode so we have a complete address.",
    "phone": "Use a 10-digit mobile number.",
    "email": "Add your email id so your team can reach you.",
    "short_bio": "Your bio needs more than 40 words. This is what your clients see about you.",
    "degree": "Add at least one degree (title and year).",
    "services_offered": "Select at least one service you offer.",
}


def word_count(text: str | None) -> int:
    if not text:
        return 0
    clipped = text.strip()[:BIO_MAX_CHARS]
    return len([part for part in clipped.split() if part])


def normalize_phone_digits(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def is_ten_digit_phone(phone: str | None) -> bool:
    return len(normalize_phone_digits(phone)) == 10


def is_six_digit_pincode(pincode: str | None) -> bool:
    return bool(pincode and PINCODE_RE.match(str(pincode).strip()))


def normalize_qualification_entries(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [
            {"kind": "certificate", "title": line.strip(), "year": None}
            for line in raw.splitlines()
            if line.strip()
        ]
    entries: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            title = item.strip()
            if title:
                entries.append({"kind": "certificate", "title": title, "year": None})
            continue
        if not isinstance(item, dict):
            continue
        kind = (item.get("kind") or "certificate").strip().lower()
        if kind not in ("degree", "certificate"):
            kind = "certificate"
        title = (item.get("title") or "").strip()
        if not title:
            continue
        year = item.get("year")
        try:
            year_int = int(year) if year not in (None, "") else None
        except (TypeError, ValueError):
            year_int = None
        if year_int is not None and not (YEAR_MIN <= year_int <= YEAR_MAX):
            year_int = None
        entries.append({"kind": kind, "title": title[:255], "year": year_int})
    return entries


def flatten_qualification_entries(entries: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    degrees = [e for e in entries if e.get("kind") == "degree"]
    certs = [e for e in entries if e.get("kind") == "certificate"]

    def _label(entry: dict[str, Any]) -> str:
        title = entry.get("title") or ""
        year = entry.get("year")
        return f"{title} ({year})" if year else title

    academic = "; ".join(_label(e) for e in degrees if e.get("title")) or None
    certificates = [_label(e) for e in certs if e.get("title")]
    return academic, certificates


def has_complete_degree(entries: list[dict[str, Any]]) -> bool:
    return any(
        e.get("kind") == "degree" and e.get("title") and e.get("year") is not None for e in entries
    )


def _pincode_from_user(user: Any) -> str | None:
    pin = getattr(user, "home_pincode", None)
    if pin:
        return pin
    home = getattr(user, "home_address", None)
    if isinstance(home, dict):
        return home.get("pincode") or home.get("home_pincode")
    return getattr(home, "pincode", None) if home is not None else None


def evaluate_profile_quality(
    user: Any,
    profile: Any | None = None,
    *,
    listing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score contact + listing fields. `listing` overlays pending/form values."""
    listing = listing or {}
    pending = getattr(profile, "pending_submission", None) if profile is not None else None
    source: dict[str, Any] = {}
    if profile is not None:
        source["display_name"] = getattr(profile, "display_name", None)
        source["short_bio"] = getattr(profile, "short_bio", None)
        source["services_offered"] = list(getattr(profile, "services_offered", None) or [])
        source["professional_qualification_entries"] = list(
            getattr(profile, "professional_qualification_entries", None) or []
        )
        if not source["professional_qualification_entries"]:
            source["professional_qualification_entries"] = list(
                getattr(profile, "professional_certificates", None) or []
            )
    if pending:
        source.update({k: pending[k] for k in pending})
    source.update(listing)

    entries = normalize_qualification_entries(source.get("professional_qualification_entries"))
    services = source.get("services_offered") or []
    bio = source.get("short_bio") or ""
    display_name = (source.get("display_name") or getattr(user, "full_name", None) or "").strip()
    line1 = (getattr(user, "home_address_line1", None) or "").strip()
    city = (getattr(user, "home_city", None) or "").strip()
    if not line1 or not city:
        home = getattr(user, "home_address", None)
        if isinstance(home, dict):
            line1 = line1 or (home.get("address_line1") or "").strip()
            city = city or (home.get("city") or "").strip()
        elif home is not None:
            line1 = line1 or (getattr(home, "address_line1", None) or "").strip()
            city = city or (getattr(home, "city", None) or "").strip()

    checks = {
        "avatar": bool((getattr(user, "avatar_path", None) or getattr(user, "avatar_url", None) or "").strip()),
        "home_address": bool(line1 and city),
        "pincode": is_six_digit_pincode(_pincode_from_user(user)),
        "phone": is_ten_digit_phone(getattr(user, "phone", None)),
        "email": bool((getattr(user, "email", None) or "").strip()),
        "short_bio": word_count(bio) > BIO_MIN_WORDS,
        "degree": has_complete_degree(entries),
        "services_offered": len(services) > 0,
    }

    items = []
    reminders = []
    score = 0
    for key, weight in QUALITY_WEIGHTS.items():
        passed = bool(checks[key])
        items.append({"key": key, "passed": passed, "points": weight if passed else 0, "max": weight})
        if passed:
            score += weight
        else:
            reminders.append({"key": key, "message": REMINDERS[key]})

    auto_pass = (
        score > 80
        and checks["avatar"]
        and checks["pincode"]
        and checks["short_bio"]
        and checks["degree"]
    )
    can_submit = score >= 50 and bool(display_name)
    return {
        "score": score,
        "percent": score,
        "items": items,
        "reminders": reminders,
        "can_submit": can_submit,
        "auto_pass": auto_pass,
        "word_count": word_count(bio),
    }

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.models.case import Case
from app.models.user import User
from app.schemas.address import AddressRead, format_address_summary, maps_query_url

HOME_PREFIX = "home_"
SCHOOL_PREFIX = "school_"
SERVICE_PREFIX = "service_"

ADDRESS_ATTRS = (
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "landmark",
    "latitude",
    "longitude",
)


def is_homecare_case(case: Case) -> bool:
    if (case.product_module or "").lower() == "homecare":
        return True
    return "homecare" in (case.service_type or "").lower()


def _has_any_address_value(data: dict[str, Any], prefix: str) -> bool:
    for attr in ADDRESS_ATTRS:
        key = f"{prefix}{attr}" if prefix else attr
        val = data.get(key)
        if val is not None and val != "":
            return True
    return False


def _get_prefixed(obj: Any, prefix: str) -> dict[str, Any]:
    return {attr: getattr(obj, f"{prefix}{attr}", None) for attr in ADDRESS_ATTRS}


def _address_read_from_prefixed(values: dict[str, Any]) -> AddressRead | None:
    if not values.get("address_line1"):
        return None
    formatted = format_address_summary(
        values.get("address_line1"),
        values.get("address_line2"),
        values.get("city"),
        values.get("state"),
        values.get("pincode"),
        values.get("landmark"),
    )
    url = maps_query_url(values.get("latitude"), values.get("longitude"), formatted)
    return AddressRead(
        address_line1=values.get("address_line1"),
        address_line2=values.get("address_line2"),
        city=values.get("city"),
        state=values.get("state"),
        pincode=values.get("pincode"),
        landmark=values.get("landmark"),
        latitude=values.get("latitude"),
        longitude=values.get("longitude"),
        formatted=formatted,
        maps_url=url,
    )


def user_home_address_read(user: User) -> AddressRead | None:
    return _address_read_from_prefixed(_get_prefixed(user, HOME_PREFIX))


def user_school_address_read(user: User) -> AddressRead | None:
    return _address_read_from_prefixed(_get_prefixed(user, SCHOOL_PREFIX))


def case_service_address_read(case: Case) -> AddressRead | None:
    return _address_read_from_prefixed(_get_prefixed(case, SERVICE_PREFIX))


def service_address_summary(case: Case) -> str | None:
    addr = case_service_address_read(case)
    return addr.formatted if addr else None


def _validate_user_address_payload(data: dict[str, Any], prefix: str, label: str) -> None:
    if not _has_any_address_value(data, prefix):
        return
    text_keys = tuple(f"{prefix}{attr}" for attr in ("address_line1", "city", "pincode", "address_line2", "state", "landmark"))
    if not any(k in data for k in text_keys):
        return
    line1 = data.get(f"{prefix}address_line1")
    city = data.get(f"{prefix}city")
    pincode = data.get(f"{prefix}pincode")
    if not line1 or not city or not pincode:
        raise HTTPException(
            status_code=400,
            detail=f"{label} requires address line 1, city, and pincode when saving",
        )
    from app.schemas.address import PINCODE_RE

    if pincode and not PINCODE_RE.match(str(pincode)):
        raise HTTPException(status_code=400, detail="Pincode must be exactly 6 digits")


def validate_home_address_payload(data: dict[str, Any]) -> None:
    _validate_user_address_payload(data, HOME_PREFIX, "Home address")


def validate_school_address_payload(data: dict[str, Any]) -> None:
    _validate_user_address_payload(data, SCHOOL_PREFIX, "School address")


def validate_service_address_payload(data: dict[str, Any], case: Case) -> None:
    if not is_homecare_case(case):
        return
    if not _has_any_address_value(data, SERVICE_PREFIX):
        return
    text_keys = (
        "service_address_line1",
        "service_city",
        "service_pincode",
        "service_address_line2",
        "service_state",
        "service_landmark",
    )
    if not any(k in data for k in text_keys):
        return
    line1 = data.get("service_address_line1")
    city = data.get("service_city")
    pincode = data.get("service_pincode")
    if not line1 or not city or not pincode:
        raise HTTPException(
            status_code=400,
            detail="Service address requires address_line1, city, and pincode for homecare cases",
        )
    from app.schemas.address import PINCODE_RE

    if pincode and not PINCODE_RE.match(str(pincode)):
        raise HTTPException(status_code=400, detail="Pincode must be exactly 6 digits")


def _apply_user_address(user: User, data: dict[str, Any], prefix: str) -> None:
    for attr in ADDRESS_ATTRS:
        key = f"{prefix}{attr}"
        if key in data:
            setattr(user, key, data[key])


def apply_home_address_to_user(user: User, data: dict[str, Any]) -> None:
    _apply_user_address(user, data, HOME_PREFIX)
    if user.home_city and user.home_pincode:
        user.location = f"{user.home_city}, {user.home_pincode}"


def apply_school_address_to_user(user: User, data: dict[str, Any]) -> None:
    _apply_user_address(user, data, SCHOOL_PREFIX)


def apply_service_address_to_case(case: Case, data: dict[str, Any]) -> None:
    for attr in ADDRESS_ATTRS:
        key = f"service_{attr}"
        if key in data:
            setattr(case, key, data[key])


def _user_address_from_update(payload: dict[str, Any], field_prefix: str) -> dict[str, Any]:
    """Map API home_* / school_* fields to DB column keys."""
    mapping = {
        f"{field_prefix}address_line1": f"{field_prefix}address_line1",
        f"{field_prefix}address_line2": f"{field_prefix}address_line2",
        f"{field_prefix}city": f"{field_prefix}city",
        f"{field_prefix}state": f"{field_prefix}state",
        f"{field_prefix}pincode": f"{field_prefix}pincode",
        f"{field_prefix}landmark": f"{field_prefix}landmark",
        f"{field_prefix}latitude": f"{field_prefix}latitude",
        f"{field_prefix}longitude": f"{field_prefix}longitude",
    }
    return {k: payload[v] for k, v in mapping.items() if v in payload and payload[v] is not None}


def home_address_from_me_update(payload: dict[str, Any]) -> dict[str, Any]:
    return _user_address_from_update(payload, HOME_PREFIX)


def school_address_from_parent_update(payload: dict[str, Any]) -> dict[str, Any]:
    return _user_address_from_update(payload, SCHOOL_PREFIX)


def service_address_from_payload(payload: dict[str, Any], prefix_keys: bool = True) -> dict[str, Any]:
    """Map AddressFields API names to service_* columns."""
    out: dict[str, Any] = {}
    for attr in ADDRESS_ATTRS:
        api_key = attr
        db_key = f"service_{attr}"
        if api_key in payload and payload[api_key] is not None:
            out[db_key] = payload[api_key]
        elif prefix_keys and db_key in payload:
            out[db_key] = payload[db_key]
    return out

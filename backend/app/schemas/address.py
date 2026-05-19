from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote_plus

from pydantic import BaseModel, field_validator

PINCODE_RE = re.compile(r"^[0-9]{6}$")


class AddressFields(BaseModel):
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not PINCODE_RE.match(v):
            raise ValueError("Pincode must be exactly 6 digits")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class AddressRead(AddressFields):
    formatted: Optional[str] = None
    maps_url: Optional[str] = None


class ServiceAddressUpdate(AddressFields):
    """Parent or admin PATCH body for case service location."""

    pass


def format_address_summary(
    address_line1: Optional[str],
    address_line2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    pincode: Optional[str] = None,
    landmark: Optional[str] = None,
) -> str:
    parts: list[str] = []
    if address_line1:
        parts.append(address_line1.strip())
    if address_line2:
        parts.append(address_line2.strip())
    if landmark:
        parts.append(f"Near {landmark.strip()}")
    city_pin: list[str] = []
    if city:
        city_pin.append(city.strip())
    if state:
        city_pin.append(state.strip())
    if pincode:
        city_pin.append(pincode.strip())
    if city_pin:
        parts.append(", ".join(city_pin))
    return ", ".join(parts)


def maps_query_url(
    latitude: Optional[float],
    longitude: Optional[float],
    formatted_address: str,
) -> str:
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(formatted_address)}"

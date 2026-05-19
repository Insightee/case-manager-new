from __future__ import annotations

import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/geocode", tags=["geocode"])


def _pick_address_part(address: dict, keys: list[str]) -> str:
    for key in keys:
        val = address.get(key)
        if val and isinstance(val, str):
            return val
    return ""


@router.get("/reverse")
def reverse_geocode(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Proxy reverse geocoding (avoids browser CORS limits on Nominatim)."""
    qs = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
    )
    url = f"https://nominatim.openstreetmap.org/reverse?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "InsightCase/1.0 (contact@insighte.local)",
            "Accept": "application/json",
            "Accept-Language": "en",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json

            data = json.loads(resp.read().decode())
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Reverse geocode failed") from exc

    address = data.get("address") or {}
    house = " ".join(filter(None, [address.get("house_number"), address.get("house_name")]))
    road = address.get("road") or address.get("pedestrian") or ""
    line1 = " ".join(filter(None, [house, road])).strip() or (data.get("display_name") or "").split(",")[0]
    pincode = _pick_address_part(address, ["postcode"])
    pincode_digits = "".join(c for c in pincode if c.isdigit())[:6]

    return {
        "address_line1": line1,
        "address_line2": _pick_address_part(address, ["suburb", "neighbourhood", "quarter"]),
        "city": _pick_address_part(address, ["city", "town", "village", "county", "state_district"]),
        "state": _pick_address_part(address, ["state", "region"]),
        "pincode": pincode_digits if len(pincode_digits) == 6 else pincode_digits,
        "landmark": _pick_address_part(address, ["amenity", "shop"]),
        "latitude": lat,
        "longitude": lon,
    }

"""Shared OYO search and pricing helpers routed through Tabby execute/fetch."""

from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.oyorooms.com"
DEFAULT_PROFILE = "oyo"


def _display_date(value: str) -> str:
    """Convert an ISO date to the DD/MM/YYYY format expected by OYO."""
    parsed = date.fromisoformat(value)
    return parsed.strftime("%d/%m/%Y")


def _destination_slug(destination: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", destination.strip().lower()).strip("-")
    if not slug:
        raise ValueError("destination must contain letters or numbers")
    return slug


def _preloaded_state(html: str) -> dict[str, Any]:
    marker = "__PRELOADED_STATE__"
    marker_index = html.find(marker)
    if marker_index < 0:
        raise RuntimeError("OYO page did not contain __PRELOADED_STATE__")
    assignment_index = html.find("=", marker_index)
    script_end = html.find("</script>", assignment_index)
    if assignment_index < 0 or script_end < 0:
        raise RuntimeError("Could not locate the OYO preloaded-state boundary")
    payload = html[assignment_index + 1 : script_end].strip().removesuffix(";")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OYO preloaded state was not valid JSON") from exc


def _money(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def normalize_hotel(hotel: dict[str, Any]) -> dict[str, Any]:
    pricing = hotel.get("pricing") or {}
    tax_info = pricing.get("taxInfo") or {}
    rating = hotel.get("rating") or {}
    path = hotel.get("url") or f"/{hotel.get('id', '')}/"
    url = path if str(path).startswith("http") else urllib.parse.urljoin(BASE_URL, str(path))
    amenities = list(
        dict.fromkeys(
            item.get("displayName")
            for item in hotel.get("amenities") or []
            if isinstance(item, dict) and item.get("displayName")
        )
    )
    return {
        "hotel_id": str(hotel.get("id") or ""),
        "name": hotel.get("name") or "",
        "address": hotel.get("address") or "",
        "city": hotel.get("city") or "",
        "category": hotel.get("category") or "",
        "rating": rating.get("value"),
        "rating_count": rating.get("count"),
        "rating_label": rating.get("subtext") or rating.get("rating_level") or "",
        "available": not bool(hotel.get("isSoldOut")),
        "currency": hotel.get("currency_symbol") or "₹",
        "base_price": _money(pricing.get("bookingPrice")),
        "slashed_price": _money(pricing.get("slashedPrice")),
        "discount_percentage": _money(pricing.get("discountPercentage")),
        "tax_amount": _money(tax_info.get("total_tax")),
        "total_with_tax": _money(tax_info.get("final_price_with_tax")),
        "amenities": amenities,
        "url": url,
    }


async def search_destinations(
    query: str,
    *,
    profile_slug: str = DEFAULT_PROFILE,
    limit: int = 10,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "region": "1",
            "additionalFields": "rating,supply,trending,tags,category",
        }
    )
    data = await execute_fetch(
        profile_slug,
        f"{BASE_URL}/api/pwa/autocompletenew?{params}",
        headers={"referer": f"{BASE_URL}/"},
    )
    suggestions = data.get("responseObject", []) if isinstance(data, dict) else []
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "display_name": item.get("displayName"),
            "location_type": item.get("locationType"),
            "city": (item.get("city") or {}).get("name"),
            "state": (item.get("state") or {}).get("name"),
            "country": (item.get("country") or {}).get("name"),
            "latitude": (item.get("centerPoint") or {}).get("lat"),
            "longitude": (item.get("centerPoint") or {}).get("lng"),
        }
        for item in suggestions[: max(1, limit)]
    ]


async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    *,
    rooms: int = 1,
    adults: int = 2,
    children: int = 0,
    profile_slug: str = DEFAULT_PROFILE,
) -> dict[str, Any]:
    if date.fromisoformat(check_out) <= date.fromisoformat(check_in):
        raise ValueError("check_out must be after check_in")
    if rooms < 1 or adults < 1 or children < 0:
        raise ValueError("rooms/adults must be positive and children cannot be negative")

    slug = _destination_slug(destination)
    room_config = f"{rooms}-{adults}_{children}"
    params = {
        "checkin": _display_date(check_in),
        "checkout": _display_date(check_out),
        "rooms": str(rooms),
        "guests": str(adults),
        "rooms_config": room_config,
    }
    search_url = f"{BASE_URL}/hotels-in-{slug}/?{urllib.parse.urlencode(params)}"
    response = await execute_fetch(
        profile_slug,
        search_url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    if not html:
        raise RuntimeError("OYO returned an empty hotel-search page")
    state = _preloaded_state(html)
    listing = state.get("listing") or {}
    hotels = [normalize_hotel(item) for item in listing.get("hotels") or []]
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "rooms": rooms,
        "adults": adults,
        "children": children,
        "search_url": search_url,
        "total_results": listing.get("total") or listing.get("count") or len(hotels),
        "results_count": len(hotels),
        "hotels": hotels,
    }


def find_hotel(search_result: dict[str, Any], hotel_id: str) -> dict[str, Any]:
    match = next(
        (hotel for hotel in search_result.get("hotels", []) if hotel["hotel_id"] == hotel_id),
        None,
    )
    if not match:
        raise RuntimeError(f"Hotel {hotel_id!r} was not present on the first OYO results page")
    return match

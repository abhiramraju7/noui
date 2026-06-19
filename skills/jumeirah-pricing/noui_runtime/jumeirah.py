"""Jumeirah public hotel discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.jumeirah.com"
DEFAULT_PROFILE = "jumeirah-hotels"


def _validate_stay(check_in: str, check_out: str, rooms: int, adults: int, children: int) -> None:
    if date.fromisoformat(check_out) <= date.fromisoformat(check_in):
        raise ValueError("check_out must be after check_in")
    if rooms < 1 or adults < 1 or children < 0:
        raise ValueError("rooms/adults must be positive and children cannot be negative")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _visible_text(value: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


def _next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, flags=re.S
    )
    if not match:
        raise RuntimeError("Jumeirah page did not contain __NEXT_DATA__")
    return json.loads(html_module.unescape(match.group(1)))


def _find_booking_list(value: Any) -> str:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and '"regions"' in item and '"Hotels"' in item:
            return item
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    raise RuntimeError("Jumeirah booking property list was not found")


async def _properties(profile_slug: str) -> list[dict[str, Any]]:
    response = await execute_fetch(
        profile_slug,
        f"{BASE_URL}/en",
        headers={"accept": "text/html"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    data = json.loads(_find_booking_list(_next_data(html)))
    properties: list[dict[str, Any]] = []
    for region in data.get("regions") or []:
        region_parts = str(region.get("Value") or "").split("|")
        region_name = region_parts[1] if len(region_parts) > 1 else ""
        for city in region.get("Cities") or []:
            city_parts = str(city.get("Value") or "").split("|")
            city_name = city_parts[1] if len(city_parts) > 1 else ""
            city_code = city_parts[2] if len(city_parts) > 2 else ""
            for hotel in city.get("Hotels") or []:
                parts = str(hotel.get("Value") or "").split("|")
                if len(parts) < 3:
                    continue
                hotel_id, code, name = parts[:3]
                page_slug = _slug(name.replace(" a Jumeirah Partner Hotel", ""))
                properties.append(
                    {
                        "hotel_id": hotel_id,
                        "hotel_code": code,
                        "name": name,
                        "city": city_name,
                        "city_code": city_code,
                        "region": region_name,
                        "url": f"{BASE_URL}/en/stay/{_slug(city_name)}/{page_slug}",
                    }
                )
    return properties


def _booking_url(
    hotel: dict[str, Any], check_in: str, check_out: str, rooms: int, adults: int, children: int
) -> str:
    query = urllib.parse.urlencode(
        {
            "hotel": hotel["hotel_code"],
            "hotelId": hotel["hotel_id"],
            "checkIn": check_in,
            "checkOut": check_out,
            "rooms": rooms,
            "adults": adults,
            "children": children,
        }
    )
    return f"{BASE_URL}/en/booking/hotel-booking?{query}"


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    properties = await _properties(profile_slug)
    matches = {
        (item["city"], item["city_code"], item["region"])
        for item in properties
        if query.lower() in item["city"].lower() or query.lower() in item["region"].lower()
    }
    return [
        {"city": city, "city_code": code, "region": region}
        for city, code, region in sorted(matches)[: max(1, limit)]
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
    _validate_stay(check_in, check_out, rooms, adults, children)
    hotels = [
        item
        for item in await _properties(profile_slug)
        if destination.lower() in item["city"].lower()
        or destination.lower() in item["region"].lower()
        or destination.lower() in item["name"].lower()
    ]
    for hotel in hotels:
        hotel["booking_url"] = _booking_url(hotel, check_in, check_out, rooms, adults, children)
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "rooms": rooms,
        "adults": adults,
        "children": children,
        "results_count": len(hotels),
        "hotels": hotels,
    }


def find_hotel(search_result: dict[str, Any], hotel_id: str) -> dict[str, Any]:
    match = next(
        (
            item
            for item in search_result.get("hotels", [])
            if item["hotel_id"] == hotel_id
            or item["hotel_code"].lower() == hotel_id.lower()
            or item["name"].lower() == hotel_id.lower()
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"Jumeirah hotel {hotel_id!r} was not found")
    return match


async def _hotel_html(hotel: dict[str, Any], profile_slug: str) -> str:
    response = await execute_fetch(
        profile_slug,
        hotel["url"],
        headers={"accept": "text/html", "referer": f"{BASE_URL}/en"},
        timeout_ms=60_000,
    )
    return response.get("text", "") if isinstance(response, dict) else ""


async def get_hotel_amenities(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> list[str]:
    text = _visible_text(await _hotel_html(hotel, profile_slug))
    known = (
        "pool",
        "spa",
        "beach",
        "fitness",
        "wifi",
        "restaurant",
        "kids club",
        "concierge",
    )
    return [value for value in known if re.search(rf"\b{re.escape(value)}\b", text, re.I)]


def _extract_rates(value: str) -> list[dict[str, Any]]:
    text = _visible_text(value)
    found: dict[tuple[str, float], dict[str, Any]] = {}
    for match in re.finditer(
        r"(?P<currency>AED|USD|EUR|GBP|CNY|IDR|MVR|KWD|BHD|OMR|SAR|₹|\$|€|£)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)",
        text,
        flags=re.I,
    ):
        amount = float(match.group("amount").replace(",", ""))
        if amount > 0:
            key = (match.group("currency").upper(), amount)
            found[key] = {"currency": key[0], "amount": key[1]}
    return sorted(found.values(), key=lambda item: item["amount"])


async def get_hotel_rates(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    response = await execute_fetch(
        profile_slug,
        hotel["booking_url"],
        headers={"accept": "text/html", "referer": hotel["url"]},
        timeout_ms=60_000,
    )
    value = response.get("text", "") if isinstance(response, dict) else json.dumps(response)
    rates = _extract_rates(value)
    return {
        "hotel_id": hotel["hotel_id"],
        "hotel_code": hotel["hotel_code"],
        "name": hotel["name"],
        "available": True if rates else None,
        "lowest_rate": rates[0] if rates else None,
        "rates": rates,
        "booking_url": hotel["booking_url"],
        "pricing_note": "Rates are dynamic; null means the booking page did not expose a rate to fetch.",
    }

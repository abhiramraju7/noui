"""Taj public hotel discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.tajhotels.com"
DEFAULT_PROFILE = "taj-hotels"


def _validate_stay(check_in: str, check_out: str, rooms: int, adults: int, children: int) -> None:
    if date.fromisoformat(check_out) <= date.fromisoformat(check_in):
        raise ValueError("check_out must be after check_in")
    if rooms < 1 or adults < 1 or children < 0:
        raise ValueError("rooms/adults must be positive and children cannot be negative")


def _hotel_url(item: dict[str, Any]) -> str:
    path = str(item.get("path") or "").lstrip("/")
    if path.startswith("hotels/") or path.startswith("palace/"):
        return f"{BASE_URL}/en-in/{path}"
    identifier = item.get("identifier") or ""
    return f"{BASE_URL}/en-in/hotels/{identifier}/rooms-and-suites"


def _booking_url(
    item: dict[str, Any], check_in: str, check_out: str, rooms: int, adults: int, children: int
) -> str:
    page = _hotel_url(item).rstrip("/")
    if not page.endswith("booking"):
        page += "/booking"
    query = urllib.parse.urlencode(
        {
            "from": check_in,
            "to": check_out,
            "overrideSessionDates": "true",
            "rooms": rooms,
            "adults": adults,
            "children": children,
        }
    )
    return f"{page}?{query}"


def normalize_hotel(item: dict[str, Any]) -> dict[str, Any]:
    availability = item.get("hotel_Availability") or {}
    address = item.get("hotelAddress") or {}
    taxonomy = item.get("searchTaxonomies") or {}
    return {
        "hotel_id": str(item.get("hotelId") or item.get("id") or ""),
        "synxis_hotel_id": str(item.get("synxis_hotel_id") or taxonomy.get("synxisHotelId") or ""),
        "hotel_code": item.get("hotel_code") or taxonomy.get("hotelCode") or "",
        "identifier": item.get("identifier") or "",
        "name": item.get("hotelName") or item.get("name") or "",
        "brand": item.get("brandName") or item.get("brand_name") or "Taj",
        "city": address.get("city") or item.get("city") or "",
        "state": address.get("state") or item.get("hotel_state") or "",
        "country": address.get("country") or item.get("hotel_country") or "",
        "postal_code": address.get("pincode") or item.get("hotel_pin_code") or "",
        "hotel_type": taxonomy.get("hotelType") or item.get("hotel_type") or "",
        "address": ", ".join(
            str(value)
            for value in (
                address.get("addressLine1"),
                address.get("addressLine2"),
                address.get("street"),
                address.get("city"),
                address.get("state"),
                address.get("pincode"),
                address.get("country"),
            )
            if value
        ),
        "description": item.get("description") or "",
        "amenities": item.get("facilities") or [],
        "check_in_out": availability.get("check_in") or [],
        "inventory_summary": availability.get("rooms") or [],
        "url": _hotel_url(item),
    }


def _destination_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("destination must contain letters or numbers")
    return slug


def _next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, flags=re.S
    )
    if not match:
        raise RuntimeError("Taj destination page did not contain __NEXT_DATA__")
    return json.loads(html_module.unescape(match.group(1)))


def _hotel_records(value: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("hotelId") and item.get("hotelName") and item.get("identifier"):
                key = str(item["hotelId"])
                found[key] = item
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return list(found.values())


async def _destination_hotels(
    destination: str, *, profile_slug: str = DEFAULT_PROFILE
) -> tuple[str, list[dict[str, Any]]]:
    url = f"{BASE_URL}/en-in/destination/hotels-in-{_destination_slug(destination)}"
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/en-in"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    if not html:
        raise RuntimeError("Taj returned an empty destination page")
    data = _next_data(html)
    destination_data = data.get("props", {}).get("pageProps", {}).get("destinationData", [])
    if destination_data and isinstance(destination_data[0], dict):
        hotels = destination_data[0].get("participatingHotels") or []
        if hotels:
            return url, hotels
    return url, _hotel_records(data)


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    _, hotels = await _destination_hotels(query, profile_slug=profile_slug)
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in hotels:
        address = item.get("hotelAddress") or {}
        key = (address.get("city") or "", address.get("state") or "", address.get("country") or "")
        if key[0] and key not in seen:
            seen[key] = {"city": key[0], "state": key[1], "country": key[2]}
    return list(seen.values())[: max(1, limit)]


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
    search_url, raw_hotels = await _destination_hotels(destination, profile_slug=profile_slug)
    hotels = [normalize_hotel(item) for item in raw_hotels]
    raw_by_id = {str(item.get("hotelId") or item.get("id") or ""): item for item in raw_hotels}
    for hotel in hotels:
        hotel["booking_url"] = _booking_url(
            raw_by_id[hotel["hotel_id"]], check_in, check_out, rooms, adults, children
        )
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "rooms": rooms,
        "adults": adults,
        "children": children,
        "search_url": search_url,
        "results_count": len(hotels),
        "hotels": hotels,
    }


def find_hotel(search_result: dict[str, Any], hotel_id: str) -> dict[str, Any]:
    match = next(
        (
            item
            for item in search_result.get("hotels", [])
            if item["hotel_id"] == hotel_id or item["identifier"] == hotel_id
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"Taj hotel {hotel_id!r} was not found in the destination results")
    return match


def _visible_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


async def get_hotel_amenities(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> list[str]:
    if hotel.get("amenities"):
        return list(hotel["amenities"])
    response = await execute_fetch(
        profile_slug,
        hotel["url"],
        headers={"accept": "text/html", "referer": f"{BASE_URL}/en-in"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    candidates = re.findall(
        r"(?:amenit(?:y|ies)|facilit(?:y|ies))[^<]{0,80}</[^>]+>\s*<[^>]+>([^<]{2,80})",
        html,
        flags=re.I,
    )
    return list(dict.fromkeys(_visible_text(value) for value in candidates if value.strip()))


def _extract_rates(html: str) -> list[dict[str, Any]]:
    text = _visible_text(html)
    patterns = (
        r"(?P<currency>INR|AED|USD|EUR|GBP|₹|\$|€|£)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)",
        r"(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)\s*(?P<currency>INR|AED|USD|EUR|GBP)",
    )
    rates: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            amount = float(match.group("amount").replace(",", ""))
            if amount <= 0:
                continue
            currency = match.group("currency").upper()
            key = (currency, amount)
            if key not in seen:
                seen.add(key)
                rates.append({"currency": currency, "amount": amount})
    return sorted(rates, key=lambda item: item["amount"])


async def get_hotel_rates(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    response = await execute_fetch(
        profile_slug,
        hotel["booking_url"],
        headers={"accept": "text/html", "referer": hotel["url"]},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    rates = _extract_rates(html)
    return {
        "hotel_id": hotel["hotel_id"],
        "name": hotel["name"],
        "available": bool(rates),
        "lowest_rate": rates[0] if rates else None,
        "rates": rates,
        "booking_url": hotel["booking_url"],
        "pricing_note": "Public rates are live and may change until reservation confirmation.",
    }

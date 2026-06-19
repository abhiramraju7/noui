"""NH Hotels public discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.nh-hotels.com"
DEFAULT_PROFILE = "nh-hotels"


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


async def _destination_page(destination: str, profile_slug: str) -> tuple[str, str]:
    url = f"{BASE_URL}/en/hotels/{_slug(destination)}"
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/en"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    if not html:
        raise RuntimeError("NH Hotels returned an empty destination page")
    return url, html


def _balanced_object(source: str, marker: str) -> dict[str, Any]:
    start = source.find(marker)
    if start < 0:
        raise RuntimeError(f"NH Hotels page did not contain {marker}")
    start = source.find("{", start)
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(source[start : index + 1])
    raise RuntimeError("NH Hotels embedded data object was incomplete")


def _hotel_records(html: str) -> list[dict[str, Any]]:
    data = _balanced_object(html, "let beanDatalayer")
    links: dict[str, str] = {}
    for href, body in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S
    ):
        label = _visible_text(body)
        if label and ("NH " in label or "nhow" in label.lower()):
            links[label.lower()] = urllib.parse.urljoin(BASE_URL, href)
    hotels = []
    for item in data.get("hotels") or []:
        name = str(item.get("name") or "")
        page_url = next((url for label, url in links.items() if name.lower() in label), "")
        hotels.append(
            {
                "hotel_id": str(item.get("id") or ""),
                "content_code": item.get("code") or "",
                "name": name,
                "brand": item.get("brand") or "",
                "stars": item.get("stars"),
                "url": page_url,
            }
        )
    return hotels


def _display_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def _booking_url(
    hotel: dict[str, Any], check_in: str, check_out: str, rooms: int, adults: int, children: int
) -> str:
    base = hotel.get("url") or f"{BASE_URL}/en/hotel/{_slug(hotel['name'])}"
    query = urllib.parse.urlencode(
        {
            "fini": _display_date(check_in),
            "fout": _display_date(check_out),
            "rooms": rooms,
            "adults": adults,
            "children": children,
            "hotelId": hotel["hotel_id"],
        }
    )
    return f"{base}?{query}"


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    url, html = await _destination_page(query, profile_slug)
    data = _balanced_object(html, "let beanDatalayer")
    booking = data.get("bookingProcess") or {}
    return [
        {
            "city": booking.get("city") or query,
            "country": booking.get("country") or "",
            "country_code": booking.get("countryCode") or "",
            "url": url,
            "hotel_count": len(data.get("hotels") or []),
        }
    ][: max(1, limit)]


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
    search_url, html = await _destination_page(destination, profile_slug)
    hotels = _hotel_records(html)
    for hotel in hotels:
        hotel["booking_url"] = _booking_url(hotel, check_in, check_out, rooms, adults, children)
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
            if item["hotel_id"] == hotel_id or item["name"].lower() == hotel_id.lower()
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"NH Hotels property {hotel_id!r} was not found")
    return match


async def _hotel_html(hotel: dict[str, Any], profile_slug: str) -> str:
    if not hotel.get("url"):
        return ""
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
        "free wifi",
        "parking",
        "fitness center",
        "pool",
        "spa",
        "restaurant",
        "pet friendly",
        "meeting rooms",
    )
    return [value for value in known if value in text.lower()]


def _extract_rates(value: str) -> list[dict[str, Any]]:
    text = _visible_text(value)
    found: dict[tuple[str, float], dict[str, Any]] = {}
    for match in re.finditer(
        r"(?P<currency>EUR|USD|GBP|CHF|COP|ARS|MXN|BRL|€|\$|£)\s*(?P<amount>[0-9][0-9.,]*)",
        text,
        flags=re.I,
    ):
        raw = match.group("amount").replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            continue
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
        headers={"accept": "text/html", "referer": f"{BASE_URL}/en"},
        timeout_ms=60_000,
    )
    value = response.get("text", "") if isinstance(response, dict) else json.dumps(response)
    rates = _extract_rates(value)
    return {
        "hotel_id": hotel["hotel_id"],
        "name": hotel["name"],
        "available": True if rates else None,
        "lowest_rate": rates[0] if rates else None,
        "rates": rates,
        "booking_url": hotel["booking_url"],
        "pricing_note": "Rates are dynamic; null means the booking page did not expose a rate to fetch.",
    }

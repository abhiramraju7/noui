"""Oberoi public hotel discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.oberoihotels.com"
BOOKING_URL = "https://res.oberoihotels.com"
DEFAULT_PROFILE = "oberoi-hotels"


def _validate_stay(check_in: str, check_out: str, rooms: int, adults: int, children: int) -> None:
    if date.fromisoformat(check_out) <= date.fromisoformat(check_in):
        raise ValueError("check_out must be after check_in")
    if rooms < 1 or adults < 1 or children < 0:
        raise ValueError("rooms/adults must be positive and children cannot be negative")


def _visible_text(value: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


async def _home_html(profile_slug: str) -> str:
    response = await execute_fetch(
        profile_slug,
        f"{BASE_URL}/",
        headers={"accept": "text/html"},
        timeout_ms=60_000,
    )
    html = response.get("text", "") if isinstance(response, dict) else ""
    if not html:
        raise RuntimeError("Oberoi returned an empty homepage")
    return html


def _hotel_records(html: str) -> list[dict[str, Any]]:
    links: dict[str, str] = {}
    for href, text in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S
    ):
        label = _visible_text(text)
        if label and ("Oberoi" in label or "Wildflower Hall" in label):
            links[label.lower()] = urllib.parse.urljoin(BASE_URL, href)
    found: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r'<li[^>]+data-hotelcode=["\'](?P<code>[^"\']+)["\'][^>]+'
        r'data-city=["\'](?P<city>[^"\']*)["\'][^>]+'
        r'data-hotelName=["\'](?P<name>[^"\']+)["\'][^>]*>(?P<label>.*?)</li>',
        re.I | re.S,
    )
    for match in pattern.finditer(html):
        code = html_module.unescape(match.group("code")).strip()
        name = html_module.unescape(match.group("name")).strip()
        city = html_module.unescape(match.group("city")).strip()
        label = _visible_text(match.group("label"))
        page_url = next(
            (url for key, url in links.items() if name.lower() in key or key in label.lower()), ""
        )
        found[code] = {
            "hotel_id": code,
            "hotel_code": code,
            "name": name,
            "city": city,
            "label": label,
            "url": page_url,
        }
    return list(found.values())


def _booking_url(
    hotel: dict[str, Any], check_in: str, check_out: str, rooms: int, adults: int, children: int
) -> str:
    query = urllib.parse.urlencode(
        {
            "adult": adults,
            "arrive": check_in,
            "chain": "24188",
            "child": children,
            "depart": check_out,
            "hotel": hotel["hotel_code"],
            "level": "hotel",
            "locale": "en-US",
            "rooms": rooms,
        }
    )
    return f"{BOOKING_URL}/?{query}"


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    hotels = _hotel_records(await _home_html(profile_slug))
    names = sorted({item["city"] for item in hotels if query.lower() in item["city"].lower()})
    return [{"city": city} for city in names[: max(1, limit)]]


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
        for item in _hotel_records(await _home_html(profile_slug))
        if destination.lower() in item["city"].lower()
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
            if item["hotel_id"] == hotel_id or item["name"].lower() == hotel_id.lower()
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"Oberoi hotel {hotel_id!r} was not found")
    return match


async def _hotel_html(hotel: dict[str, Any], profile_slug: str) -> str:
    if not hotel.get("url"):
        return ""
    response = await execute_fetch(
        profile_slug,
        hotel["url"],
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
        timeout_ms=60_000,
    )
    return response.get("text", "") if isinstance(response, dict) else ""


async def get_hotel_amenities(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> list[str]:
    html = await _hotel_html(hotel, profile_slug)
    values = re.findall(
        r'<(?:li|h[2-5]|span)[^>]*class=["\'][^"\']*(?:amenit|facilit)[^"\']*["\'][^>]*>(.*?)</(?:li|h[2-5]|span)>',
        html,
        flags=re.I | re.S,
    )
    return list(dict.fromkeys(_visible_text(value) for value in values if _visible_text(value)))


def _extract_rates(value: str) -> list[dict[str, Any]]:
    text = _visible_text(value)
    rates: dict[tuple[str, float], dict[str, Any]] = {}
    for match in re.finditer(
        r"(?P<currency>INR|AED|USD|EUR|GBP|₹|\$|€|£)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)",
        text,
        flags=re.I,
    ):
        amount = float(match.group("amount").replace(",", ""))
        if amount > 0:
            key = (match.group("currency").upper(), amount)
            rates[key] = {"currency": key[0], "amount": key[1]}
    return sorted(rates.values(), key=lambda item: item["amount"])


async def get_hotel_rates(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    try:
        response = await execute_fetch(
            profile_slug,
            hotel["booking_url"],
            headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
            timeout_ms=60_000,
        )
        html = response.get("text", "") if isinstance(response, dict) else json.dumps(response)
        rates = _extract_rates(html)
    except RuntimeError:
        rates = []
    return {
        "hotel_id": hotel["hotel_id"],
        "name": hotel["name"],
        "available": True if rates else None,
        "lowest_rate": rates[0] if rates else None,
        "rates": rates,
        "booking_url": hotel["booking_url"],
        "pricing_note": "Rates are live and may change; null means the booking engine did not expose a rate to fetch.",
    }

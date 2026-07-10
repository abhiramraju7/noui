"""Banyan Tree Hotels public discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.banyantree.com"
DEFAULT_PROFILE = "banyan-tree"
ALLOWED_HOSTS = {"www.banyantree.com", "banyantree.com"}


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


async def _fetch_page(url: str, profile_slug: str) -> str:
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
        timeout_ms=60_000,
    )
    status = int(response.get("status", 0)) if isinstance(response, dict) else 0
    if status >= 400:
        raise RuntimeError(f"Banyan Tree Hotels returned HTTP {status} for {url}")
    html = response.get("text", "") if isinstance(response, dict) else ""
    if not html:
        raise RuntimeError("Banyan Tree Hotels returned an empty public page")
    return html


async def _destination_page(destination: str, profile_slug: str) -> tuple[str, str]:
    slug = _slug(destination)
    candidates = [
        f"{BASE_URL}/?{urllib.parse.urlencode({'search': destination})}",
        f"{BASE_URL}/destinations/{slug}",
        f"{BASE_URL}/hotels/{slug}",
    ]
    last_error: Exception | None = None
    for url in candidates:
        try:
            return url, await _fetch_page(url, profile_slug)
        except RuntimeError as exc:
            last_error = exc
    raise RuntimeError(f"Banyan Tree Hotels destination lookup failed: {last_error}")


def _json_ld_records(page: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        kind = value.get("@type", "")
        kinds = (
            {str(item).lower() for item in kind} if isinstance(kind, list) else {str(kind).lower()}
        )
        if kinds & {"hotel", "lodgingbusiness", "resort", "localbusiness"}:
            name = str(value.get("name") or "").strip()
            if name:
                raw_url = str(value.get("url") or value.get("@id") or "")
                url = urllib.parse.urljoin(BASE_URL, raw_url)
                parsed = urllib.parse.urlparse(url)
                if parsed.netloc and parsed.netloc not in ALLOWED_HOSTS:
                    url = ""
                rating = value.get("aggregateRating") or {}
                found[url or name.lower()] = {
                    "hotel_id": url or _slug(name),
                    "name": name,
                    "brand": "Banyan Tree",
                    "stars": None,
                    "url": url,
                    "description": _visible_text(str(value.get("description") or ""))[:500],
                    "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
                }
        for child in value.values():
            if isinstance(child, (dict, list)):
                visit(child)

    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.I | re.S,
    ):
        try:
            visit(json.loads(html_module.unescape(block)))
        except (json.JSONDecodeError, TypeError):
            continue
    return list(found.values())


def _link_records(page: str, destination: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    hints = ("banyan", "hotel", "resort", "villas", "suite", "destination")
    destination_tokens = {token for token in re.split(r"\W+", destination.lower()) if token}
    for href, body in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        page,
        flags=re.I | re.S,
    ):
        label = _visible_text(body)
        if not label or len(label) > 220:
            continue
        url = urllib.parse.urljoin(BASE_URL, html_module.unescape(href))
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc and parsed.netloc not in ALLOWED_HOSTS:
            continue
        haystack = f"{label} {url}".lower()
        if not any(hint in haystack for hint in hints):
            continue
        if destination_tokens and not any(token in haystack for token in destination_tokens):
            continue
        found[url] = {
            "hotel_id": url or _slug(label),
            "name": label,
            "brand": "Banyan Tree",
            "stars": None,
            "url": url,
            "description": "",
            "rating": None,
        }
    return list(found.values())


def _hotel_records(page: str, destination: str) -> list[dict[str, Any]]:
    records = {item["hotel_id"]: item for item in _json_ld_records(page)}
    for item in _link_records(page, destination):
        records.setdefault(item["hotel_id"], item)
    return list(records.values())


def _booking_url(
    hotel: dict[str, Any], check_in: str, check_out: str, rooms: int, adults: int, children: int
) -> str:
    base = hotel.get("url") or BASE_URL
    query = urllib.parse.urlencode(
        {
            "checkin": check_in,
            "checkout": check_out,
            "rooms": rooms,
            "adults": adults,
            "children": children,
        }
    )
    separator = "&" if urllib.parse.urlparse(base).query else "?"
    return f"{base}{separator}{query}"


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    url, page = await _destination_page(query, profile_slug)
    hotels = _hotel_records(page, query)
    return [
        {
            "city": query,
            "country": "",
            "country_code": "",
            "url": url,
            "hotel_count": len(hotels),
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
    search_url, page = await _destination_page(destination, profile_slug)
    hotels = _hotel_records(page, destination)
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
            if item["hotel_id"] == hotel_id
            or item["name"].lower() == hotel_id.lower()
            or item.get("url") == hotel_id
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"Banyan Tree Hotels property {hotel_id!r} was not found")
    return match


async def _hotel_html(hotel: dict[str, Any], profile_slug: str) -> str:
    if not hotel.get("url"):
        return ""
    return await _fetch_page(hotel["url"], profile_slug)


async def get_hotel_amenities(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> list[str]:
    text = _visible_text(await _hotel_html(hotel, profile_slug)).lower()
    known = (
        "free wifi",
        "wifi",
        "pool",
        "spa",
        "restaurant",
        "bar",
        "fitness",
        "wellbeing",
        "beach",
        "villas",
        "meeting",
        "airport transfer",
    )
    return [value for value in known if value in text]


def _extract_rates(value: str) -> list[dict[str, Any]]:
    text = _visible_text(value)
    found: dict[tuple[str, float], dict[str, Any]] = {}
    pattern = (
        r"(?P<currency>USD|EUR|GBP|SGD|THB|AED|INR|IDR|MYR|AUD|CAD|₹|\$|€|£)"
        r"\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)"
    )
    for match in re.finditer(pattern, text, flags=re.I):
        raw = match.group("amount").replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            continue
        if 0 < amount < 1_000_000:
            key = (match.group("currency").upper(), amount)
            found[key] = {"currency": key[0], "amount": key[1]}
    return sorted(found.values(), key=lambda item: item["amount"])[:50]


async def get_hotel_rates(
    hotel: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    response = await execute_fetch(
        profile_slug,
        hotel["booking_url"],
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
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
        "pricing_note": (
            "Rates are dynamic public snapshots; null means the booking page did not expose "
            "a parseable rate through execute/fetch."
        ),
    }

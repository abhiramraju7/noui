"""Public travel-meta discovery through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

PLATFORM = "Momondo"
BASE_URL = "https://www.momondo.in"
PROFILE = "momondo"
MODE = "flights"
ALLOWED_HOSTS = {"momondo.com", "www.momondo.com", "momondo.in", "www.momondo.in"}


def _text(value: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html_module.unescape(value)).strip()


def _validate_dates(start: str, end: str) -> None:
    if start and end and date.fromisoformat(end) <= date.fromisoformat(start):
        raise ValueError("end date must be after start date")


def _build_url(
    *,
    query: str,
    origin: str,
    destination: str,
    departure: str,
    return_date: str,
    check_in: str,
    check_out: str,
    pickup: str,
    dropoff: str,
    adults: int,
) -> str:
    _validate_dates(departure, return_date)
    _validate_dates(check_in, check_out)
    platform = PLATFORM.lower()
    destination = destination or query

    if platform == "google travel":
        if MODE == "flights":
            phrase = f"Flights from {origin} to {destination}"
            if departure:
                phrase += f" departing {departure}"
            if return_date:
                phrase += f" returning {return_date}"
            return f"{BASE_URL}/travel/flights?{urllib.parse.urlencode({'q': phrase})}"
        if MODE == "hotels":
            phrase = f"Hotels in {destination}"
            return f"{BASE_URL}/travel/search?{urllib.parse.urlencode({'q': phrase})}"
        return f"{BASE_URL}/travel/explore?{urllib.parse.urlencode({'q': destination or query})}"

    if platform == "momondo":
        if MODE == "flights" and origin and destination and departure:
            route = f"{origin.upper()}-{destination.upper()}/{departure}"
            if return_date:
                route += f"/{return_date}"
            return f"{BASE_URL}/flight-search/{route}?sort=bestflight_a"
        if MODE == "stays":
            params = {"destination": destination, "checkin": check_in, "checkout": check_out}
            return f"{BASE_URL}/stays?{urllib.parse.urlencode(params)}"
        if MODE == "cars":
            params = {"pickup": pickup or destination, "dropoff": dropoff or pickup}
            return f"{BASE_URL}/car-rental?{urllib.parse.urlencode(params)}"

    if platform == "hopper":
        tab = {"flights": "flights", "stays": "stays", "cars": "cars"}.get(MODE, MODE)
        params = {
            "activeTab": tab,
            "origin": origin,
            "destination": destination,
            "departure": departure,
            "return": return_date,
            "checkIn": check_in,
            "checkOut": check_out,
            "pickup": pickup,
            "dropoff": dropoff,
            "adults": adults,
        }
        return f"{BASE_URL}/?{urllib.parse.urlencode({k: v for k, v in params.items() if v})}"

    if platform == "tripadvisor":
        if MODE == "reviews":
            return f"{BASE_URL}/Search?{urllib.parse.urlencode({'q': query or destination})}"
        params = {
            "searchQuery": destination,
            "checkIn": check_in,
            "checkOut": check_out,
            "adults": adults,
        }
        return f"{BASE_URL}/Hotels?{urllib.parse.urlencode({k: v for k, v in params.items() if v})}"

    if platform == "trivago":
        params = {
            "search": destination,
            "checkin": check_in,
            "checkout": check_out,
            "adults": adults,
        }
        return f"{BASE_URL}/en-US?{urllib.parse.urlencode({k: v for k, v in params.items() if v})}"

    return f"{BASE_URL}/?{urllib.parse.urlencode({'q': query or destination})}"


async def _fetch(url: str, profile_slug: str) -> str:
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
        timeout_ms=60_000,
    )
    status = int(response.get("status", 0)) if isinstance(response, dict) else 0
    if status >= 400:
        raise RuntimeError(f"{PLATFORM} returned HTTP {status} for {url}")
    page = response.get("text", "") if isinstance(response, dict) else ""
    if not page:
        raise RuntimeError(f"{PLATFORM} returned an empty public page")
    return page


def _json_records(page: str) -> list[dict[str, Any]]:
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
        if kinds & {
            "hotel",
            "lodgingbusiness",
            "accommodation",
            "touristattraction",
            "flight",
            "product",
            "place",
        }:
            name = str(value.get("name") or "").strip()
            url = urllib.parse.urljoin(BASE_URL, str(value.get("url") or value.get("@id") or ""))
            if name:
                key = url or name.lower()
                rating = value.get("aggregateRating") or {}
                offers = value.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                found[key] = {
                    "id": str(value.get("identifier") or key),
                    "name": name,
                    "url": url,
                    "description": _text(str(value.get("description") or ""))[:500],
                    "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
                    "review_count": rating.get("reviewCount") if isinstance(rating, dict) else None,
                    "price": offers.get("price") if isinstance(offers, dict) else None,
                    "currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
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


def _link_records(page: str, query: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    mode_hints = {
        "flights": ("flight", "airport", "airline"),
        "hotels": ("hotel", "lodging", "stay"),
        "stays": ("hotel", "lodging", "stay"),
        "cars": ("car", "rental"),
        "explore": ("travel", "explore", "destination"),
        "reviews": ("review", "hotel", "attraction", "restaurant"),
        "pricing": ("hotel", "deal", "price"),
        "properties": ("hotel", "property"),
    }.get(MODE, (MODE,))
    for href, inner in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.I | re.S
    ):
        label = _text(inner)
        url = urllib.parse.urljoin(BASE_URL, html_module.unescape(href))
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc and parsed.netloc not in ALLOWED_HOSTS:
            continue
        haystack = f"{label} {url}".lower()
        if not label or len(label) > 240:
            continue
        matches_query = bool(query and query.lower() in haystack)
        matches_mode = any(hint in haystack for hint in mode_hints)
        if matches_query or (not query and matches_mode):
            found[url] = {"id": url, "name": label, "url": url}
    return list(found.values())


def _prices(page: str) -> list[dict[str, Any]]:
    text = _text(page)
    values: dict[tuple[str, float], dict[str, Any]] = {}
    pattern = r"(?P<currency>USD|EUR|GBP|AUD|CAD|INR|AED|₹|\$|€|£)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)"
    for match in re.finditer(pattern, text, flags=re.I):
        amount = float(match.group("amount").replace(",", ""))
        if 0 < amount < 1_000_000:
            key = (match.group("currency").upper(), amount)
            values[key] = {"currency": key[0], "amount": amount}
    return sorted(values.values(), key=lambda item: item["amount"])[:50]


async def run_public_search(
    *,
    query: str = "",
    origin: str = "",
    destination: str = "",
    departure: str = "",
    return_date: str = "",
    check_in: str = "",
    check_out: str = "",
    pickup: str = "",
    dropoff: str = "",
    url: str = "",
    adults: int = 1,
    limit: int = 20,
    profile_slug: str = PROFILE,
) -> dict[str, Any]:
    if adults < 1:
        raise ValueError("adults must be positive")
    if url:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc not in ALLOWED_HOSTS:
            raise ValueError(f"url must belong to {PLATFORM}")
        source_url = url
    else:
        source_url = _build_url(
            query=query,
            origin=origin,
            destination=destination,
            departure=departure,
            return_date=return_date,
            check_in=check_in,
            check_out=check_out,
            pickup=pickup,
            dropoff=dropoff,
            adults=adults,
        )
    page = await _fetch(source_url, profile_slug)
    lookup = destination or query
    structured = _json_records(page)
    if lookup:
        needle = lookup.lower()
        structured = [
            item
            for item in structured
            if needle
            in f"{item.get('name', '')} {item.get('url', '')} {item.get('description', '')}".lower()
        ]
    records = structured or _link_records(page, lookup)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.I | re.S)
    return {
        "platform": PLATFORM,
        "mode": MODE,
        "source_url": source_url,
        "title": _text(title_match.group(1)) if title_match else "",
        "results_count": len(records[: max(1, limit)]),
        "results": records[: max(1, limit)],
        "prices": _prices(page),
        "public_summary": _text(page)[:2000],
        "note": "Public meta-search prices are snapshots and may change on the booking provider.",
    }

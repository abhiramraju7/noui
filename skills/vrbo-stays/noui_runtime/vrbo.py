"""Public Vrbo discovery and pricing through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.vrbo.com"
DEFAULT_PROFILE = "vrbo"
PROPERTY_HINTS = ("/p/", "/vacation-rental/", "/listing/")
SEARCH_PATH = "/searchResults.html"
DESTINATION_PARAM = "destination"
CHECKIN_PARAM = "startDate"
CHECKOUT_PARAM = "endDate"
GUESTS_PARAM = "adults"
IGNORE_LABELS = {"login", "sign up", "menu", "home", "book now", "view all"}


def _validate_stay(check_in: str, check_out: str, rooms: int, adults: int, children: int) -> None:
    if date.fromisoformat(check_out) <= date.fromisoformat(check_in):
        raise ValueError("check_out must be after check_in")
    if rooms < 1 or adults < 1 or children < 0:
        raise ValueError("rooms/adults must be positive and children cannot be negative")


def _visible_text(value: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html_module.unescape(value)).strip()


async def _fetch_html(profile_slug: str, url: str) -> str:
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/"},
        timeout_ms=60_000,
    )
    status = int(response.get("status", 0)) if isinstance(response, dict) else 0
    if status == 429:
        raise RuntimeError(
            "Vrbo returned HTTP 429 inside the Tabby session; retry after the site rate limit clears"
        )
    if status >= 400:
        raise RuntimeError(f"Vrbo returned HTTP {status} for {url}")
    body = response.get("text", "") if isinstance(response, dict) else ""
    if not body:
        raise RuntimeError("Vrbo returned an empty page")
    return body


def _json_ld_records(page: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.I | re.S,
    )

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
        if kinds & {"hotel", "hostel", "lodgingbusiness", "accommodation", "product"}:
            name = str(value.get("name") or "").strip()
            if name:
                offer = value.get("offers") or {}
                if isinstance(offer, list):
                    offer = offer[0] if offer else {}
                records.append(
                    {
                        "stay_id": str(
                            value.get("identifier") or value.get("@id") or value.get("url") or name
                        ),
                        "name": name,
                        "url": urllib.parse.urljoin(BASE_URL, str(value.get("url") or "")),
                        "description": _visible_text(str(value.get("description") or "")),
                        "rating": (value.get("aggregateRating") or {}).get("ratingValue"),
                        "price": offer.get("price") if isinstance(offer, dict) else None,
                        "currency": offer.get("priceCurrency") if isinstance(offer, dict) else None,
                    }
                )
        for child in value.values():
            if isinstance(child, (dict, list)):
                visit(child)

    for block in blocks:
        try:
            visit(json.loads(html_module.unescape(block)))
        except (json.JSONDecodeError, TypeError):
            continue
    return records


def _link_records(page: str, destination: str = "") -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for href, inner in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.I | re.S
    ):
        url = urllib.parse.urljoin(BASE_URL, html_module.unescape(href))
        label = _visible_text(inner)
        if not label or label.lower() in IGNORE_LABELS or len(label) > 180:
            continue
        path = urllib.parse.urlparse(url).path.lower()
        if not any(hint in path for hint in PROPERTY_HINTS):
            continue
        if destination and destination.lower() not in f"{label} {url}".lower():
            continue
        records[url] = {"stay_id": url, "name": label, "url": url}
    return list(records.values())


def _extract_rates(value: str) -> list[dict[str, Any]]:
    text = _visible_text(value)
    rates: dict[tuple[str, float], dict[str, Any]] = {}
    pattern = r"(?P<currency>USD|EUR|GBP|AUD|CAD|INR|AED|₹|\$|€|£)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)"
    for match in re.finditer(pattern, text, flags=re.I):
        amount = float(match.group("amount").replace(",", ""))
        if 0 < amount < 1_000_000:
            key = (match.group("currency").upper(), amount)
            rates[key] = {"currency": key[0], "amount": amount}
    return sorted(rates.values(), key=lambda item: item["amount"])


def _search_url(destination: str, check_in: str, check_out: str, adults: int) -> str:
    query = urllib.parse.urlencode(
        {
            DESTINATION_PARAM: destination,
            CHECKIN_PARAM: check_in,
            CHECKOUT_PARAM: check_out,
            GUESTS_PARAM: adults,
        }
    )
    return f"{BASE_URL}{SEARCH_PATH}?{query}"


async def search_destinations(
    query: str, *, profile_slug: str = DEFAULT_PROFILE, limit: int = 10
) -> list[dict[str, Any]]:
    page = await _fetch_html(profile_slug, f"{BASE_URL}/")
    found: dict[str, dict[str, Any]] = {}
    for href, inner in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.I | re.S
    ):
        label = _visible_text(inner)
        if query.lower() in label.lower() and 1 < len(label) < 100:
            url = urllib.parse.urljoin(BASE_URL, href)
            found[label.lower()] = {"name": label, "url": url}
    return list(found.values())[: max(1, limit)]


async def search_stays(
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
    url = _search_url(destination, check_in, check_out, adults + children)
    page = await _fetch_html(profile_slug, url)
    stays = _json_ld_records(page) or _link_records(page, destination)
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "rooms": rooms,
        "adults": adults,
        "children": children,
        "results_count": len(stays),
        "stays": stays,
        "search_url": url,
    }


def find_stay(search_result: dict[str, Any], stay_id: str) -> dict[str, Any]:
    match = next(
        (
            item
            for item in search_result.get("stays", [])
            if item["stay_id"] == stay_id or item["name"].lower() == stay_id.lower()
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"Vrbo stay {stay_id!r} was not found")
    return match


async def _stay_html(stay: dict[str, Any], profile_slug: str) -> str:
    url = stay.get("url")
    return await _fetch_html(profile_slug, url) if url else ""


async def get_stay_amenities(
    stay: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> list[str]:
    page = await _stay_html(stay, profile_slug)
    values = re.findall(
        r'<(?:li|span|div)[^>]*class=["\'][^"\']*(?:amenit|facilit)[^"\']*["\'][^>]*>(.*?)</(?:li|span|div)>',
        page,
        flags=re.I | re.S,
    )
    return list(dict.fromkeys(_visible_text(value) for value in values if _visible_text(value)))


async def get_stay_rates(
    stay: dict[str, Any], *, profile_slug: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    page = await _stay_html(stay, profile_slug)
    rates = _extract_rates(page)
    return {
        "stay_id": stay["stay_id"],
        "name": stay["name"],
        "url": stay.get("url"),
        "available": bool(rates),
        "rates": rates,
        "lowest_rate": rates[0] if rates else None,
        "note": "Public page prices may exclude taxes, fees, or member-only discounts.",
    }

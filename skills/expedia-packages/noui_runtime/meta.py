"""Public travel-meta discovery through Tabby execute/fetch."""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.parse
from datetime import date
from typing import Any

from noui_runtime.execute import execute_fetch

PLATFORM = "Expedia"
BASE_URL = "https://www.expedia.com"
PROFILE = "expedia"
MODE = "packages"
ALLOWED_HOSTS = {"expedia.com", "www.expedia.com"}


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
    common = {
        "destination": destination,
        "origin": origin,
        "departure": departure,
        "return": return_date,
        "checkin": check_in,
        "checkout": check_out,
        "pickup": pickup or destination,
        "dropoff": dropoff or pickup,
        "adults": adults,
    }

    def with_query(path: str, values: dict[str, Any] | None = None) -> str:
        params = values or common
        encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value})
        return f"{BASE_URL}{path}" + (f"?{encoded}" if encoded else "")

    if platform == "booking.com":
        paths = {
            "stays": "/searchresults.html",
            "flights": "/flights/index.en-gb.html",
            "cars": "/cars/index.en-gb.html",
            "attractions": "/attractions/searchresults.html",
            "airport-taxis": "/taxi/index.en-gb.html",
        }
        values = {**common, "ss": destination, "query": destination}
        return with_query(paths.get(MODE, "/"), values)

    if platform in {"expedia", "hotels.com", "orbitz"}:
        paths = {
            "stays": "/Hotel-Search",
            "hotels": "/Hotel-Search",
            "vacation-rentals": "/lp/b/vacation-rentals",
            "properties": "/Hotel-Search",
            "pricing": "/Hotel-Search",
            "flights": "/Flights-Search",
            "cars": "/Cars-Search",
            "packages": "/Packages",
            "activities": "/Things-To-Do",
            "cruises": "/Cruises",
        }
        values = {
            **common,
            "startDate": check_in or departure,
            "endDate": check_out or return_date,
        }
        return with_query(paths.get(MODE, "/"), values)

    if platform == "airbnb":
        slug = urllib.parse.quote(destination or query)
        paths = {
            "homes": f"/s/{slug}/homes",
            "pricing": f"/s/{slug}/homes",
            "experiences": f"/s/{slug}/experiences",
            "services": f"/s/{slug}/services",
        }
        values = {**common, "tab_id": f"{MODE}_tab"}
        return with_query(paths.get(MODE, "/"), values)

    if platform == "trip.com":
        paths = {
            "hotels": "/hotels/list",
            "flights": "/flights/showfarefirst",
            "trains": "/trains/list",
            "cars": "/carhire/list",
            "attractions": "/things-to-do/list",
        }
        values = {
            **common,
            "city": destination,
            "dcity": origin,
            "acity": destination,
            "ddate": departure,
            "rdate": return_date,
            "search": destination,
        }
        return with_query(paths.get(MODE, "/"), values)

    if platform == "agoda":
        paths = {
            "hotels": "/search",
            "homes": "/homes",
            "flights": "/flights/results",
            "packages": "/packages",
            "activities": "/activities",
            "transfers": "/airport-transfer",
        }
        return with_query(paths.get(MODE, "/"), {**common, "city": destination})

    if platform == "kayak":
        if MODE == "flights" and origin and destination and departure:
            route = f"{origin.upper()}-{destination.upper()}/{departure}"
            if return_date:
                route += f"/{return_date}"
            return f"{BASE_URL}/flights/{route}?sort=bestflight_a"
        paths = {
            "stays": "/hotels",
            "cars": "/cars",
            "explore": f"/explore/{origin.upper()}" if origin else "/explore",
            "packages": "/packages",
        }
        return with_query(paths.get(MODE, "/"))

    if platform == "skyscanner":
        if MODE == "flights" and origin and destination and departure:
            depart = departure.replace("-", "")[2:]
            returned = return_date.replace("-", "")[2:] if return_date else ""
            route = f"{origin.lower()}/{destination.lower()}/{depart}"
            if returned:
                route += f"/{returned}"
            return f"{BASE_URL}/transport/flights/{route}/"
        paths = {"hotels": "/hotels", "cars": "/carhire", "explore": "/flights"}
        return with_query(paths.get(MODE, "/"))

    if platform == "priceline":
        paths = {
            "hotels": "/",
            "flights": "/flights",
            "cars": "/rental-cars",
            "packages": "/packages",
            "cruises": "/cruises",
            "experiences": "/experiences",
        }
        return with_query(paths.get(MODE, "/"), {**common, "product": MODE})

    return with_query("/", {"q": query or destination})


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

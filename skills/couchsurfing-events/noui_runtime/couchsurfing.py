"""Couchsurfing public place, community, and event discovery via Tabby."""

from __future__ import annotations

import html as html_module
import re
import urllib.parse
from typing import Any

from noui_runtime.execute import execute_fetch

BASE_URL = "https://www.couchsurfing.com"
DEFAULT_PROFILE = "couchsurfing"


def _text(value: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html_module.unescape(value)).strip()


async def _fetch(url: str, profile_slug: str) -> str:
    response = await execute_fetch(
        profile_slug,
        url,
        headers={"accept": "text/html", "referer": f"{BASE_URL}/places/"},
        timeout_ms=60_000,
    )
    status = int(response.get("status", 0)) if isinstance(response, dict) else 0
    if status >= 400:
        raise RuntimeError(f"Couchsurfing returned HTTP {status} for {url}")
    page = response.get("text", "") if isinstance(response, dict) else ""
    if not page:
        raise RuntimeError("Couchsurfing returned an empty public page")
    return page


def _links(page: str, path_hint: str, query: str = "") -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for href, inner in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.I | re.S
    ):
        url = urllib.parse.urljoin(BASE_URL, html_module.unescape(href))
        label = _text(inner)
        if path_hint not in urllib.parse.urlparse(url).path.lower() or not label:
            continue
        if query and query.lower() not in f"{label} {url}".lower():
            continue
        found[url] = {"name": label[:200], "url": url, "id": url.rstrip("/").rsplit("/", 1)[-1]}
    return list(found.values())


async def search_places(
    query: str, *, limit: int = 10, profile_slug: str = DEFAULT_PROFILE
) -> list[dict[str, Any]]:
    page = await _fetch(f"{BASE_URL}/places/", profile_slug)
    records = _links(page, "/c/locations/", query)
    return records[: max(1, limit)]


async def list_popular_places(
    *, limit: int = 20, profile_slug: str = DEFAULT_PROFILE
) -> list[dict[str, Any]]:
    page = await _fetch(f"{BASE_URL}/places/", profile_slug)
    return _links(page, "/c/locations/")[: max(1, limit)]


async def get_public_page(url: str, *, profile_slug: str = DEFAULT_PROFILE) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc not in {
        "www.couchsurfing.com",
        "couchsurfing.com",
    }:
        raise ValueError("url must be a couchsurfing.com public page")
    page = await _fetch(url, profile_slug)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.I | re.S)
    description = re.search(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        page,
        flags=re.I,
    )
    return {
        "url": url,
        "title": _text(title_match.group(1)) if title_match else "",
        "description": html_module.unescape(description.group(1)) if description else "",
        "public_text": _text(page)[:4000],
    }


async def list_community_links(
    query: str = "", *, limit: int = 20, profile_slug: str = DEFAULT_PROFILE
) -> list[dict[str, Any]]:
    page = await _fetch(f"{BASE_URL}/places/", profile_slug)
    records = _links(page, "/c/locations/", query)
    return records[: max(1, limit)]


async def list_public_events(
    query: str = "", *, limit: int = 20, profile_slug: str = DEFAULT_PROFILE
) -> list[dict[str, Any]]:
    pages = [f"{BASE_URL}/events", f"{BASE_URL}/places/"]
    records: list[dict[str, Any]] = []
    for url in pages:
        try:
            records.extend(_links(await _fetch(url, profile_slug), "/events/", query))
        except RuntimeError:
            continue
    unique = {item["url"]: item for item in records}
    return list(unique.values())[: max(1, limit)]

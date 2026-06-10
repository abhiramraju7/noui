"""Zoho Books runtime — Tabby-routed calls against the ``/api/v3`` REST API.

Requests run via Tabby's ``POST /execute/fetch`` inside the authenticated Zoho
Books browser session. Session cookies and the SPA's CSRF injection are applied
by the browser, so no token is sniffed or passed from Python.

The ``organization_id`` is resolved from ``ZOHO_ORGANIZATION_ID``, disk cache,
or the first organization returned by ``GET /api/v3/organizations``.

Region: defaults to the India DC (``books.zoho.in``). Override with
``ZOHO_BOOKS_DOMAIN`` (e.g. ``books.zoho.com``).
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from .zoho_http import fetch_raw

DOMAIN = os.environ.get("ZOHO_BOOKS_DOMAIN", "books.zoho.in")
API_BASE = f"https://{DOMAIN}/api/v3"
ORG_CACHE = Path("/tmp/noui_zoho_org.json")
ENV_ORG = "ZOHO_ORGANIZATION_ID"

ZB_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "X-ZB-SOURCE": "zbclient",
    "Accept": "application/json",
}


def _read_org_cache() -> str | None:
    if ORG_CACHE.exists():
        try:
            return json.loads(ORG_CACHE.read_text()).get("organization_id")
        except Exception:
            return None
    return None


def _write_org_cache(org_id: str) -> None:
    try:
        ORG_CACHE.write_text(json.dumps({"organization_id": org_id}))
    except Exception:
        pass


def _parse_body(raw: str):
    try:
        return json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return raw


async def get_org_id(force: bool = False) -> str:
    """Resolve the organization_id (env override, cache, or organizations API)."""
    if not force:
        env = os.environ.get(ENV_ORG)
        if env:
            return env.strip()
        cached = _read_org_cache()
        if cached:
            return cached

    res = await fetch_raw(f"{API_BASE}/organizations", headers=ZB_HEADERS)
    if res.get("status") != 200:
        raise RuntimeError(
            f"Could not resolve Zoho organization_id ({res.get('status')}): "
            f"{str(res.get('body'))[:300]}. Set {ENV_ORG} to override."
        )
    orgs = (_parse_body(res.get("body")) or {}).get("organizations") or []
    if not orgs:
        raise RuntimeError(
            f"No organizations on this Zoho Books login. Set {ENV_ORG} or open "
            f"https://{DOMAIN} in the Tabby session."
        )
    org_id = str(orgs[0].get("organization_id") or "")
    if not org_id:
        raise RuntimeError(f"organizations response missing organization_id. Set {ENV_ORG}.")
    _write_org_cache(org_id)
    return org_id


async def books_request(
    path: str,
    method: str = "GET",
    params: dict | None = None,
    body: dict | None = None,
) -> dict:
    """Call the Zoho Books /api/v3 API inside the authenticated browser.

    Returns ``{"status": int, "body": <parsed JSON dict | raw str>}``.
    """
    org_id = await get_org_id()
    q = dict(params or {})
    q["organization_id"] = org_id
    url = f"{API_BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"

    headers = dict(ZB_HEADERS)
    fetch_body: str | None = None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        fetch_body = urllib.parse.urlencode({"JSONString": json.dumps(body)})

    res = await fetch_raw(url, method=method.upper(), body=fetch_body, headers=headers)
    status = res.get("status", 0)

    if status in (401, 403) and method.upper() not in ("GET", "HEAD"):
        await get_org_id(force=True)
        res = await fetch_raw(url, method=method.upper(), body=fetch_body, headers=headers)
        status = res.get("status", 0)

    return {"status": status, "body": _parse_body(res.get("body", ""))}

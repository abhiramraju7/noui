"""Zoho Books runtime — CDP-backed calls against the `/api/v3` REST API.

The Zoho Books web app authenticates with **session cookies** and guards write
calls with an ``X-ZCSRF-TOKEN`` header (value ``zbcsparam=<token>``). Each
operation runs ``fetch()`` *inside* Tabby's authenticated browser
(``credentials:'include'``) so cookies are attached automatically, and sniffs
the CSRF token from a live request for writes. The ``organization_id`` is parsed
from the ``books.zoho.in/app/<org>#/...`` page URL.

Region: defaults to the India DC (``books.zoho.in``). Override the data-center
host with ``ZOHO_BOOKS_DOMAIN`` (e.g. ``books.zoho.com``) and the org with
``ZOHO_ORGANIZATION_ID`` if auto-resolution is not desired.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from pathlib import Path

import httpx
import websockets

CDP_PORT = 9222
CDP_LIST_URL = f"http://localhost:{CDP_PORT}/json"
DOMAIN = os.environ.get("ZOHO_BOOKS_DOMAIN", "books.zoho.in")
PAGE_MATCH = DOMAIN
API_BASE = f"https://{DOMAIN}/api/v3"
CSRF_CACHE = Path("/tmp/noui_zoho_csrf.json")


async def _find_page() -> tuple[str | None, str | None]:
    """Return (webSocketDebuggerUrl, organization_id) for the open Zoho Books tab."""
    async with httpx.AsyncClient() as client:
        targets = (await client.get(CDP_LIST_URL, timeout=5)).json()
    for t in targets:
        if t.get("type") == "page" and PAGE_MATCH in t.get("url", ""):
            url = t.get("url", "")
            org = ""
            if "/app/" in url:
                org = url.split("/app/")[1].split("#")[0].split("/")[0].split("?")[0]
            return t["webSocketDebuggerUrl"], org
    return None, None


async def _cdp_eval(ws_url: str, expression: str):
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )
        raw = await ws.recv()
    payload = json.loads(raw)
    if "error" in payload:
        raise RuntimeError(f"CDP eval error: {json.dumps(payload['error'])[:300]}")
    result = payload.get("result", {})
    if "exceptionDetails" in result:
        raise RuntimeError(f"CDP eval threw: {json.dumps(result['exceptionDetails'])[:300]}")
    vw = result.get("result", {})
    if vw.get("type") == "string":
        return json.loads(vw["value"])
    return vw.get("value")


async def _sniff_csrf(ws_url: str, timeout: float = 20.0) -> str | None:
    """Reload the page and capture the live X-ZCSRF-TOKEN request header."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 3, "method": "Page.reload", "params": {"ignoreCache": False}}))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except TimeoutError:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            for hn, hv in msg["params"]["request"].get("headers", {}).items():
                if hn.lower() == "x-zcsrf-token" and hv:
                    return hv
    return None


def _read_csrf_cache() -> str | None:
    try:
        return json.loads(CSRF_CACHE.read_text()).get("csrf")
    except Exception:
        return None


def _write_csrf_cache(csrf: str) -> None:
    try:
        CSRF_CACHE.write_text(json.dumps({"csrf": csrf}))
    except Exception:
        pass


async def get_csrf(force: bool = False) -> str:
    """Return a valid X-ZCSRF-TOKEN, using the disk cache when present."""
    if not force:
        cached = _read_csrf_cache()
        if cached:
            return cached
    ws_url, _ = await _find_page()
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            f"`tabby session ensure --profile zoho-books --open https://{DOMAIN}`."
        )
    csrf = await _sniff_csrf(ws_url)
    if not csrf:
        raise RuntimeError(
            "Could not sniff an X-ZCSRF-TOKEN. Ensure the Zoho Books tab is open and authenticated."
        )
    _write_csrf_cache(csrf)
    return csrf


async def get_org_id() -> str:
    """Resolve the organization_id (env override or the open Books tab URL)."""
    env = os.environ.get("ZOHO_ORGANIZATION_ID")
    if env:
        return env
    _, org = await _find_page()
    if not org:
        raise RuntimeError(
            f"Could not resolve organization_id from the {DOMAIN} page URL. "
            "Set ZOHO_ORGANIZATION_ID or open the Books dashboard in the Tabby session."
        )
    return org


def _parse_body(raw: str):
    try:
        return json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return raw


async def books_request(
    path: str,
    method: str = "GET",
    params: dict | None = None,
    body: dict | None = None,
) -> dict:
    """Call the Zoho Books /api/v3 API inside the authenticated browser.

    Returns ``{"status": int, "body": <parsed JSON dict | raw str>}``. Writes
    re-sniff the CSRF token once and retry on a 401/403/CSRF rejection.
    """
    ws_url, org = await _find_page()
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            f"`tabby session ensure --profile zoho-books --open https://{DOMAIN}`."
        )
    q = dict(params or {})
    q["organization_id"] = os.environ.get("ZOHO_ORGANIZATION_ID") or org
    url = f"{API_BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"
    is_write = method.upper() not in ("GET", "HEAD")

    async def _run(csrf: str | None) -> dict:
        headers = {"X-Requested-With": "XMLHttpRequest", "X-ZB-SOURCE": "zbclient"}
        init = {"method": method.upper(), "credentials": "include", "headers": headers}
        if csrf:
            headers["X-ZCSRF-TOKEN"] = csrf
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            init["body"] = urllib.parse.urlencode({"JSONString": json.dumps(body)})
        js = (
            f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
            "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
        )
        return await _cdp_eval(ws_url, js)

    csrf = await get_csrf() if is_write else None
    res = await _run(csrf)
    status = res.get("status")
    if is_write and status in (401, 403):
        res = await _run(await get_csrf(force=True))
        status = res.get("status")
    return {"status": status, "body": _parse_body(res.get("body", ""))}

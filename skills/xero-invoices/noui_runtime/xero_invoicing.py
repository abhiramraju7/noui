"""Xero Sales/Invoicing BFF session headers.

The Sales invoice UI calls ``go.xero.com/api/invoicing/*`` with a full header
bundle (bearer + tenant + ``xero-shell-app-name: Invoicing``) captured from a
live request on the invoicing list page. Reconstructing headers from bearer alone
returns 403; this module navigates to the Sales invoicing page and sniffs the
exact headers the SPA uses.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

from .xero_account import get_tenant

CDP_PORT = 9222
CDP_LIST_URL = f"http://localhost:{CDP_PORT}/json"
PAGE_MATCH = "go.xero.com"
INVOICING_LIST = "https://go.xero.com/app/{shortcode}/invoicing/list"
INVOICING_CREATE = "https://go.xero.com/app/{shortcode}/invoicing/?optInAndDefaultToNew=true"
SNIFF_URL_PART = "/api/invoicing/customer/find"
CACHE_PATH = Path("/tmp/noui_xero_invoicing_headers.json")
HEADER_TTL = 300  # seconds; refresh before JWT expiry anyway


async def _find_page_ws() -> str | None:
    async with httpx.AsyncClient() as client:
        targets = (await client.get(CDP_LIST_URL, timeout=5)).json()
    for t in targets:
        if t.get("type") == "page" and PAGE_MATCH in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    return None


def _read_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text()) or {}
        except Exception:
            return {}
    return {}


def _write_cache(data: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(data))
    except Exception:
        pass


async def _sniff_invoicing_headers(ws_url: str, shortcode: str) -> dict:
    """Navigate to Sales invoicing list and capture headers from customer/find."""
    url = INVOICING_LIST.format(shortcode=shortcode)
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": url}}))
        deadline = asyncio.get_event_loop().time() + 25
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            except TimeoutError:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg["params"]["request"]
            if SNIFF_URL_PART in req.get("url", ""):
                headers = req.get("headers", {})
                return {
                    k: v
                    for k, v in headers.items()
                    if k.lower() not in ("content-length", "host", "referer", "origin")
                }
    raise RuntimeError(
        "Could not sniff Sales/Invoicing headers. Open go.xero.com in Tabby and "
        "ensure the invoicing list page can load."
    )


async def get_invoicing_headers(force: bool = False) -> tuple[str, dict]:
    """Return ``(ws_url, headers)`` for ``go.xero.com/api/invoicing/*`` calls."""
    cached = _read_cache()
    if (
        not force
        and cached.get("headers")
        and cached.get("fetched_at", 0) + HEADER_TTL > time.time()
    ):
        ws_url = await _find_page_ws()
        if ws_url:
            return ws_url, cached["headers"]

    ws_url = await _find_page_ws()
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run `tabby session ensure --profile xero`."
        )

    from .xero_auth import get_bearer  # local import avoids cycle at module load

    bearer = await get_bearer(force=force)
    _, shortcode = await get_tenant(ws_url, bearer, force=force)
    headers = await _sniff_invoicing_headers(ws_url, shortcode)
    _write_cache({"headers": headers, "fetched_at": time.time(), "shortcode": shortcode})
    return ws_url, headers


async def invoicing_fetch(
    ws_url: str, headers: dict, path: str, method: str = "GET", body: dict | None = None
) -> dict:
    """Call ``go.xero.com/api/invoicing/{path}`` with sniffed Sales headers."""
    from .cdp import cdp_eval

    hh = {k: v for k, v in headers.items() if k.lower() not in ("content-length",)}
    url = f"https://go.xero.com/api/invoicing/{path}"
    init: dict = {"method": method, "credentials": "omit", "headers": hh}
    if body is not None:
        hh["Content-Type"] = "application/json"
        init["headers"] = hh
        init["body"] = json.dumps(body)
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)

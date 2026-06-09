"""Xero bearer-token resolver (dynamic-header-injection pattern).

The Xero SPA holds a short-lived ``Authorization: Bearer <JWT>`` in memory and
injects it into ``go.xero.com`` and ``api.xero.com`` requests. The token is NOT
in cookies, so cookie-only CDP fetch gets 401.

This module sniffs the live bearer via CDP ``Network`` events, caches it on disk
until shortly before its JWT ``exp``, and re-sniffs on demand.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path

import httpx
import websockets

CDP_PORT = 9222
CDP_LIST_URL = f"http://localhost:{CDP_PORT}/json"
PAGE_MATCH = "go.xero.com"
CACHE_PATH = Path("/tmp/noui_xero_bearer.json")
EXP_SKEW = 120


def _jwt_exp(token: str) -> int:
    try:
        payload = token.removeprefix("Bearer ").split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get("exp", 0))
    except Exception:
        return 0


async def _find_page_ws() -> str | None:
    async with httpx.AsyncClient() as client:
        targets = (await client.get(CDP_LIST_URL, timeout=5)).json()
    for t in targets:
        if t.get("type") == "page" and PAGE_MATCH in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    return None


async def _sniff(ws_url: str, timeout: float = 25.0) -> str:
    """Reload and capture Authorization from a live go.xero.com / api.xero.com request."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        await ws.send(
            json.dumps({"id": 3, "method": "Page.reload", "params": {"ignoreCache": True}})
        )
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except TimeoutError:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg["params"]["request"]
            url = req.get("url", "")
            if "xero.com" not in url:
                continue
            headers = req.get("headers", {})
            authz = headers.get("Authorization") or headers.get("authorization") or ""
            if authz.startswith("Bearer "):
                return authz
    raise RuntimeError(
        "Could not sniff a Xero Authorization token. Ensure Tabby has go.xero.com "
        "open and authenticated (run `tabby session ensure --profile xero`)."
    )


async def get_bearer(force: bool = False) -> str:
    """Return a valid ``Bearer <jwt>`` string, using the disk cache when fresh."""
    if not force and CACHE_PATH.exists():
        try:
            token = json.loads(CACHE_PATH.read_text()).get("token", "")
            if token and _jwt_exp(token) - EXP_SKEW > time.time():
                return token
        except Exception:
            pass

    ws_url = await _find_page_ws()
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run `tabby session ensure --profile xero`."
        )
    token = await _sniff(ws_url)
    try:
        CACHE_PATH.write_text(json.dumps({"token": token}))
    except Exception:
        pass
    return token

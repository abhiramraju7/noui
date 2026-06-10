"""Xero public accounting API (``api.xero.com/api.xro/2.0``) helper.

Calls run through Tabby's ``POST /execute/fetch`` inside the authenticated Xero
browser session. The session's own auth is applied by the browser, so no bearer
token is sniffed or passed from Python. Non-secret routing headers
(``xero-tenant-id``, ``xero-tenant-shortcode``, ``xero-shell-app-name``) are
supplied here via ``xero_account``.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from .xero_account import get_tenant
from .xero_http import fetch_raw

API_BASE = "https://api.xero.com/api.xro/2.0"
SHELL_APP = "Invoicing"


async def _headers() -> dict[str, str]:
    tenant_id, shortcode = await get_tenant()
    return {
        "Accept": "application/json",
        "xero-tenant-id": tenant_id,
        "xero-tenant-shortcode": shortcode,
        "xero-shell-app-name": SHELL_APP,
        "xero-correlation-id": str(uuid.uuid4()),
    }


async def xro_request(method: str, path: str, body: Any = None) -> dict:
    """Call ``api.xro/2.0/<path>`` and return parsed JSON on 2xx."""
    headers = await _headers()
    if body is not None:
        headers["Content-Type"] = "application/json"
    res = await fetch_raw(
        f"{API_BASE}/{path}",
        method=method,
        body=body,
        headers=headers,
    )
    status = res.get("status", 0)
    raw = res.get("body", "")
    if status not in (200, 201):
        raise RuntimeError(f"Xero {method} {path} -> {status}: {raw[:300]}")
    return json.loads(raw) if raw else {}


async def xro_get(path: str) -> dict:
    return await xro_request("GET", path)


async def xro_post(path: str, body: Any) -> dict:
    return await xro_request("POST", path, body=body)


async def xro_put(path: str, body: Any) -> dict:
    return await xro_request("PUT", path, body=body)

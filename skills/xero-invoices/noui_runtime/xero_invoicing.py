"""Xero Sales/Invoicing BFF — Tabby-routed calls against go.xero.com/api/invoicing.

Requests run via Tabby's ``POST /execute/fetch`` inside the authenticated Xero
browser session. The session's own auth (cookies + the SPA's in-page fetch wrapper)
is applied by the browser, so no bearer token or header bundle is sniffed from
Python. Routing headers come from ``xero_account``.
"""

from __future__ import annotations

import uuid

from .xero_account import get_tenant
from .xero_http import fetch_raw

INVOICING_BASE = "https://go.xero.com/api/invoicing"
SHELL_APP = "Invoicing"


async def _invoicing_headers(*, force: bool = False) -> dict[str, str]:
    tenant_id, shortcode = await get_tenant(force=force)
    return {
        "Accept": "application/json",
        "xero-tenant-id": tenant_id,
        "xero-tenant-shortcode": shortcode,
        "xero-shell-app-name": SHELL_APP,
        "xero-correlation-id": str(uuid.uuid4()),
    }


async def get_invoicing_headers(force: bool = False) -> dict:
    """Return routing headers for ``go.xero.com/api/invoicing/*`` calls."""
    return await _invoicing_headers(force=force)


async def invoicing_fetch(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    *,
    headers: dict | None = None,
) -> dict:
    """Call ``go.xero.com/api/invoicing/{path}``; return ``{status, body}``."""
    hh = dict(headers or await _invoicing_headers())
    if body is not None:
        hh["Content-Type"] = "application/json"
    url = f"{INVOICING_BASE}/{path}"
    return await fetch_raw(url, method=method, body=body, headers=hh)

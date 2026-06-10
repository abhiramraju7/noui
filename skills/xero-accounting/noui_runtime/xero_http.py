"""Low-level Tabby-routed fetch for Xero.

Reuses the canonical ``execute.py`` adapter's token + endpoint helpers, but
returns the worker's raw response wrapper (target ``status`` + ``body`` text)
without raising on non-2xx, so callers can branch on Xero's status codes (e.g.
403 bearer scope on api.xro, 404 "object is NULL" on invoice/find).

``fetch()`` runs inside the authenticated Xero browser session via
``POST /execute/fetch``, so the session's own auth is applied by the browser —
no token is sniffed or passed from Python.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .execute import _get_agent_token, _tabby_api_host


def _profile_id() -> str:
    return os.environ.get("PROFILE_SLUG") or "xero"


async def fetch_raw(
    url: str,
    *,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 30_000,
) -> dict:
    """POST to Tabby ``/execute/fetch`` and return ``{status, body, headers}``.

    ``status`` and ``body`` are the *target* response's status code and raw text;
    non-2xx targets do not raise (callers inspect ``status``). Only transport-level
    failures (no session, route error) raise.
    """
    token = await _get_agent_token()

    request_body: dict[str, Any] = {
        "profile_id": _profile_id(),
        "url": url,
        "method": method.upper(),
        "timeout_ms": timeout_ms,
    }
    if headers:
        request_body["headers"] = headers
    if body is not None:
        request_body["body"] = json.dumps(body) if not isinstance(body, str) else body

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_tabby_api_host()}/execute/fetch",
            json=request_body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_ms / 1000 + 5,
        )

    if resp.status_code == 409:
        raise RuntimeError(
            f'No healthy Tabby session for profile "{_profile_id()}". '
            "Run `tabby session ensure --profile xero` or check the admin UI."
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Tabby execute/fetch failed ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    return {
        "status": data.get("status", 0),
        "body": data.get("body", "") or "",
        "headers": data.get("headers", {}),
    }

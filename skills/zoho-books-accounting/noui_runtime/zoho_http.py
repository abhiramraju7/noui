"""Low-level Tabby-routed fetch for Zoho Books.

Returns the worker's raw response wrapper (target ``status`` + ``body`` text)
without raising on non-2xx, so ``zoho_books.books_request`` can branch on status.

``fetch()`` runs inside the authenticated Zoho Books browser session via
``POST /execute/fetch``; cookies and CSRF are applied by the browser.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .execute import _get_agent_token, _tabby_api_host


def _profile_id() -> str:
    return os.environ.get("PROFILE_SLUG") or "zoho-books"


async def fetch_raw(
    url: str,
    *,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 30_000,
) -> dict:
    """POST to Tabby ``/execute/fetch`` and return ``{status, body, headers}``."""
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
        request_body["body"] = body if isinstance(body, str) else json.dumps(body)

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
            "Run `tabby session ensure --profile zoho-books` or check the admin UI."
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Tabby execute/fetch failed ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    return {
        "status": data.get("status", 0),
        "body": data.get("body", "") or "",
        "headers": data.get("headers", {}),
    }

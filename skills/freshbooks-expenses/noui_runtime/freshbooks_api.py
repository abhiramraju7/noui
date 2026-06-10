"""FreshBooks API helper — Tabby-routed requests via execute_fetch.

All FreshBooks accounting/auth API calls go through Tabby's `POST /execute/fetch`,
i.e. ``fetch()`` executed inside the authenticated FreshBooks browser session. The
session's own auth (the SPA's in-page bearer injection) is applied by the browser,
so no token is sniffed or passed from Python. Only non-secret routing headers
(``X-API-VERSION``, ``X-Account-ID``) are supplied here.
"""

from __future__ import annotations

import os
from typing import Any

from .execute import execute_fetch

API_BASE = "https://api.freshbooks.com"
API_VERSION = "2023-02-20"


def _profile_id() -> str:
    return os.environ.get("PROFILE_SLUG") or "freshbooks"


async def fb_request(
    path: str,
    method: str = "GET",
    *,
    account_id: str | None = None,
    body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """Call a FreshBooks API endpoint inside the authenticated browser session.

    Args:
        path: Absolute URL or a path relative to ``API_BASE``.
        method: HTTP method.
        account_id: Optional account id for the ``X-Account-ID`` routing header.
        body: Optional JSON-serializable request body.
        extra_headers: Optional additional non-secret headers.

    Returns:
        Parsed JSON response body on 2xx; raises RuntimeError otherwise.
    """
    headers: dict[str, str] = {"Accept": "application/json", "X-API-VERSION": API_VERSION}
    if account_id:
        headers["X-Account-ID"] = account_id
    if body is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    url = path if path.startswith("http") else f"{API_BASE}{path}"
    return await execute_fetch(_profile_id(), url, method=method, body=body, headers=headers)

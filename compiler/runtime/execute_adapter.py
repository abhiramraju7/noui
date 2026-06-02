"""Generate the noui_runtime/execute.py source code for a compiled MCP server or Skill.

Pure function — no web framework or DB dependencies.

The generated module lets operations execute HTTP calls from *inside* Tabby's
authenticated browser via the `POST /execute/fetch` HTTP endpoint on the Tabby
API. Cookies ride on `credentials: 'include'`; the real browser's TLS
fingerprint is preserved.

Requests run over plain HTTP via httpx — there is no client-side CDP or
WebSocket connection. The Tabby worker runs the actual fetch inside the
authenticated browser server-side.
"""

from __future__ import annotations


def generate_execute_adapter() -> str:
    """Generate noui_runtime/execute.py source code as a string.

    The generated module provides:
      - execute_fetch(profile_id, url, method, body, headers) — fetch inside the browser

    Returns:
        Python source code string for noui_runtime/execute.py.
    """
    return '''\
"""NoUI runtime execute adapter — fetch inside Tabby's authenticated browser session.

Shared across MCP-server and Skill output formats. Calls the Tabby API's
POST /execute/fetch endpoint, which routes to the worker pod and runs
fetch() inside the real authenticated browser via page.evaluate().

Why this module exists:
  - Cookies and TLS fingerprint come from the real authenticated browser.
  - No credential extraction on the Python side.
  - Bypasses Akamai / Cloudflare false positives that fire on httpx requests.
  - No WebSocket or CDP access needed — plain HTTP to the Tabby API.

Requires:
  - A running Tabby session for the target profile.
  - TABBY_API_URL env var (or .env) pointing to the Tabby API.
  - Agent credentials (TABBY_CLIENT_ID / TABBY_CLIENT_SECRET) for token exchange.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


def _find_env_file() -> str | None:
    """Walk up from this file to find .env, matching the auth adapter pattern."""
    if os.environ.get("NOUI_ENV_FILE"):
        return os.environ["NOUI_ENV_FILE"]
    here = Path(__file__).resolve().parent
    for _ in range(7):
        candidate = here / ".env"
        if candidate.exists():
            return str(candidate)
        here = here.parent
    for fallback in (
        Path.home() / ".config" / "noui" / ".env",
        Path.home() / ".noui" / ".env",
    ):
        if fallback.exists():
            return str(fallback)
    return None


def _load_env() -> None:
    """Best-effort dotenv load."""
    env_file = _find_env_file()
    if not env_file:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
    except ImportError:
        pass


_load_env()


def _tabby_api_host() -> str:
    """Resolve the Tabby API base URL from environment."""
    return os.environ.get("TABBY_API_URL") or "http://localhost:8000"


async def _get_agent_token() -> str:
    """Exchange client credentials for an agent bearer token.

    Reads TABBY_CLIENT_ID and TABBY_CLIENT_SECRET from env.
    Caches nothing — the caller (execute_fetch) is typically invoked once per
    tool call, and token exchange is cheap relative to the browser fetch.
    """
    client_id = os.environ.get("TABBY_CLIENT_ID", "")
    client_secret = os.environ.get("TABBY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "TABBY_CLIENT_ID and TABBY_CLIENT_SECRET must be set. "
            "Create an agent client in the Tabby admin UI."
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_tabby_api_host()}/auth/agent-token",
            json={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["access_token"]


async def execute_fetch(
    profile_id: str,
    url: str,
    *,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 30000,
) -> Any:
    """Execute fetch() inside the authenticated Tabby browser session.

    The Tabby API resolves the profile to a healthy session, routes to the
    worker pod, and runs page.evaluate(fetch(url, {credentials: \'include\'}))
    inside the real browser.

    Args:
        profile_id: Tabby profile slug (known at compile time from the workflow export).
        url: Absolute URL to fetch.
        method: HTTP method; defaults to GET.
        body: Optional JSON-serializable body.
        headers: Optional extra request headers.
        timeout_ms: Timeout in milliseconds (default 30000, max 60000).

    Returns:
        Parsed JSON body on 2xx; raises RuntimeError on non-2xx or errors.
    """
    token = await _get_agent_token()

    request_body: dict[str, Any] = {
        "profile_id": profile_id,
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

    if resp.status_code == 429:
        raise RuntimeError(f"Rate limited by Tabby API: {resp.text}")
    if resp.status_code == 409:
        raise RuntimeError(
            f"No healthy Tabby session for profile \\"{profile_id}\\". "
            "Run `tabby session ensure --profile <slug>` or check the admin UI."
        )
    if resp.status_code >= 400:
        snippet = resp.text[:500]
        raise RuntimeError(
            f"Tabby execute/fetch failed ({resp.status_code}): {snippet}"
        )

    data = resp.json()

    # The worker returns {status, headers, body} — unwrap the response body
    status = data.get("status", 0)
    raw_body = data.get("body", "")

    if not (200 <= status < 300):
        snippet = (raw_body or "")[:500]
        raise RuntimeError(f"{method.upper()} {url} -> {status}: {snippet}")

    try:
        return json.loads(raw_body) if raw_body else {}
    except (ValueError, TypeError):
        return {"status": status, "text": raw_body}
'''

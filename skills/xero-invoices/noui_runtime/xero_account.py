"""Xero tenant resolver.

Xero accounting API calls require ``xero-tenant-id`` and ``xero-tenant-shortcode``
headers alongside the bearer token. This module resolves them once at runtime:

  1. ``XERO_TENANT_ID`` / ``XERO_TENANT_SHORTCODE`` env vars (explicit override).
  2. Disk cache (``/tmp/noui_xero_account.json``).
  3. The authenticated browser page URL (shortcode from ``/app/!XXXX/``) plus the
     Xero shell organisations API (tenant UUID).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from .cdp import cdp_eval

PAGE_MATCH = "go.xero.com"
CACHE_PATH = Path("/tmp/noui_xero_account.json")
ENV_TENANT = "XERO_TENANT_ID"
ENV_SHORTCODE = "XERO_TENANT_SHORTCODE"
SHELL_APP = "Invoicing"


def _read_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text()) or {}
        except Exception:
            return {}
    return {}


def _write_cache(data: dict) -> None:
    try:
        merged = _read_cache()
        merged.update({k: v for k, v in data.items() if v})
        CACHE_PATH.write_text(json.dumps(merged))
    except Exception:
        pass


async def _shortcode_from_url(ws_url: str) -> str | None:
    info = await cdp_eval(ws_url, "JSON.stringify({path: location.pathname})")
    m = re.search(r"/app/([^/]+)/", info.get("path", ""))
    return m.group(1) if m else None


async def _tenant_from_shell(ws_url: str, bearer: str, shortcode: str) -> str | None:
    shell_url = f"https://go.xero.com/api/shell/organisations/{shortcode}"
    headers = {
        "Authorization": bearer,
        "Accept": "application/json",
        "xero-tenant-shortcode": shortcode,
        "xero-shell-app-name": SHELL_APP,
        "xero-correlation-id": str(uuid.uuid4()),
    }
    init = {"method": "GET", "credentials": "omit", "headers": headers}
    js = (
        f"fetch({json.dumps(shell_url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    res = await cdp_eval(ws_url, js)
    if res.get("status") != 200:
        return None
    body = json.loads(res["body"])
    return body.get("organisationId") or body.get("id") or body.get("tenantId")


async def _resolve(ws_url: str, bearer: str) -> dict:
    shortcode = await _shortcode_from_url(ws_url)
    if not shortcode:
        raise RuntimeError(
            "Could not read Xero org shortcode from the browser URL. Open "
            "go.xero.com/app/<shortcode>/... in Tabby, or set XERO_TENANT_SHORTCODE."
        )
    tenant_id = await _tenant_from_shell(ws_url, bearer, shortcode)
    if not tenant_id:
        raise RuntimeError(
            "Could not resolve Xero tenant id from the shell API. Set XERO_TENANT_ID to override."
        )
    resolved = {"tenant_id": tenant_id, "shortcode": shortcode}
    _write_cache(resolved)
    return resolved


async def get_tenant(ws_url: str, bearer: str, force: bool = False) -> tuple[str, str]:
    """Return ``(tenant_id, shortcode)`` for the authenticated Xero org."""
    if not force:
        env_id = os.environ.get(ENV_TENANT, "").strip()
        env_short = os.environ.get(ENV_SHORTCODE, "").strip()
        if env_id and env_short:
            return env_id, env_short
        cached = _read_cache()
        if cached.get("tenant_id") and cached.get("shortcode"):
            return cached["tenant_id"], cached["shortcode"]
    resolved = await _resolve(ws_url, bearer)
    return resolved["tenant_id"], resolved["shortcode"]

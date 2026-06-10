"""Xero tenant resolver (Tabby-routed).

Xero accounting and invoicing API calls require ``xero-tenant-id`` and
``xero-tenant-shortcode`` headers. This module resolves them once at runtime:

  1. ``XERO_TENANT_ID`` / ``XERO_TENANT_SHORTCODE`` env vars (explicit override).
  2. Disk cache (``/tmp/noui_xero_account.json``).
  3. ``GET api.xero.com/api.xro/2.0/Organisation`` through Tabby's
     ``POST /execute/fetch`` (runs inside the authenticated browser session;
     the SPA injects bearer auth automatically).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .xero_http import fetch_raw

API_BASE = "https://api.xero.com/api.xro/2.0"
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


async def _resolve() -> dict:
    headers = {
        "Accept": "application/json",
        "xero-shell-app-name": SHELL_APP,
        "xero-correlation-id": str(uuid.uuid4()),
    }
    res = await fetch_raw(f"{API_BASE}/Organisation", headers=headers)
    if res.get("status") != 200:
        raise RuntimeError(
            f"Could not resolve Xero tenant from Organisation "
            f"({res.get('status')}): {str(res.get('body'))[:300]}"
        )
    data = json.loads(res.get("body") or "{}")
    org = ((data.get("Organisations") or [{}])[0]) or {}
    tenant_id = org.get("OrganisationID")
    shortcode = org.get("ShortCode")
    if not tenant_id or not shortcode:
        raise RuntimeError(
            "Organisation response missing OrganisationID or ShortCode. "
            f"Set {ENV_TENANT} and {ENV_SHORTCODE} to override."
        )
    resolved = {"tenant_id": tenant_id, "shortcode": shortcode}
    _write_cache(resolved)
    return resolved


async def get_tenant(force: bool = False) -> tuple[str, str]:
    """Return ``(tenant_id, shortcode)`` for the authenticated Xero org."""
    if not force:
        env_id = os.environ.get(ENV_TENANT, "").strip()
        env_short = os.environ.get(ENV_SHORTCODE, "").strip()
        if env_id and env_short:
            return env_id, env_short
        cached = _read_cache()
        if cached.get("tenant_id") and cached.get("shortcode"):
            return cached["tenant_id"], cached["shortcode"]
    resolved = await _resolve()
    return resolved["tenant_id"], resolved["shortcode"]

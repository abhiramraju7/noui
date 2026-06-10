"""FreshBooks account / business resolver (Tabby-routed).

Every FreshBooks accounting API path is scoped either to an account id (e.g.
`o8QvP0`, used by invoices/expenses/clients/most reports) or to a business UUID
(used by the Profit & Loss report). Rather than hardcoding these per skill, this
module resolves them once at runtime and caches them on disk. Resolution order:

  1. `FRESHBOOKS_ACCOUNT_ID` / `FRESHBOOKS_BUSINESS_UUID` env vars (explicit override).
  2. Disk cache (`/tmp/noui_freshbooks_account.json`).
  3. The authenticated user's first business via `/auth/api/v1/users/me`,
     fetched through Tabby's `POST /execute/fetch` (so it runs inside the live
     authenticated browser session).

This lets the whole FreshBooks skill suite work against any logged-in account
without code changes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .execute import execute_fetch

ME_URL = "https://api.freshbooks.com/auth/api/v1/users/me"
CACHE_PATH = Path("/tmp/noui_freshbooks_account.json")
ENV_ACCOUNT = "FRESHBOOKS_ACCOUNT_ID"
ENV_BUSINESS = "FRESHBOOKS_BUSINESS_UUID"


def _profile_id() -> str:
    return os.environ.get("PROFILE_SLUG") or "freshbooks"


def _first_business(payload: dict) -> dict:
    """Return the first business object out of a /users/me response."""
    resp = (payload or {}).get("response", payload) or {}
    memberships = resp.get("business_memberships") or resp.get("businesses") or []
    for bm in memberships:
        if isinstance(bm, dict):
            business = bm.get("business") or bm
            if business.get("account_id") or business.get("business_uuid"):
                return business
    return {}


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
    """Fetch /users/me inside the browser and return {account_id, business_uuid}."""
    payload = await execute_fetch(_profile_id(), ME_URL, headers={"Accept": "application/json"})
    business = _first_business(payload if isinstance(payload, dict) else {})
    resolved = {
        "account_id": business.get("account_id"),
        "business_uuid": business.get("business_uuid"),
    }
    _write_cache(resolved)
    return resolved


async def get_account_id(force: bool = False) -> str:
    """Resolve the FreshBooks account id (e.g. "o8QvP0"), caching it on disk."""
    if not force:
        env_val = os.environ.get(ENV_ACCOUNT)
        if env_val:
            return env_val.strip()
        cached = _read_cache().get("account_id")
        if cached:
            return cached
    account_id = (await _resolve()).get("account_id")
    if not account_id:
        raise RuntimeError(
            f"No account id on this FreshBooks login. Set {ENV_ACCOUNT} to override."
        )
    return account_id


async def get_business_uuid(force: bool = False) -> str:
    """Resolve the FreshBooks business UUID (used by the P&L report), caching it."""
    if not force:
        env_val = os.environ.get(ENV_BUSINESS)
        if env_val:
            return env_val.strip()
        cached = _read_cache().get("business_uuid")
        if cached:
            return cached
    business_uuid = (await _resolve()).get("business_uuid")
    if not business_uuid:
        raise RuntimeError(
            f"No business uuid on this FreshBooks login. Set {ENV_BUSINESS} to override."
        )
    return business_uuid

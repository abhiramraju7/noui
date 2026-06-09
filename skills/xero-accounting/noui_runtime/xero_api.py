"""Xero public accounting API (``api.xero.com/api.xro/2.0``) helper.

These endpoints authenticate with the same in-memory bearer + tenant headers the
Xero SPA uses (see ``xero_auth`` and ``xero_account``). On this org the bearer is
scoped so read endpoints like Organisation, Accounts, TaxRates, BrandingThemes,
Currencies, and PurchaseOrders return 200, while Invoices/Reports/Payments are
403 (bearer scope, not a header issue).
"""

from __future__ import annotations

import json
import uuid

from .cdp import cdp_eval, find_page
from .xero_account import get_tenant
from .xero_auth import get_bearer

API_BASE = "https://api.xero.com/api.xro/2.0"
PAGE_MATCH = "go.xero.com"
SHELL_APP = "Invoicing"


async def _fetch(ws_url: str, bearer: str, tenant_id: str, shortcode: str, path: str) -> dict:
    url = f"{API_BASE}/{path}"
    init = {
        "method": "GET",
        "credentials": "omit",
        "headers": {
            "Authorization": bearer,
            "Accept": "application/json",
            "xero-tenant-id": tenant_id,
            "xero-tenant-shortcode": shortcode,
            "xero-shell-app-name": SHELL_APP,
            "xero-correlation-id": str(uuid.uuid4()),
        },
    }
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)


async def xro_get(path: str) -> dict:
    """GET ``api.xro/2.0/<path>`` inside Tabby's authenticated browser.

    Returns the parsed JSON body. Re-sniffs the bearer once on 401/403.
    Raises RuntimeError on non-200.
    """
    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run `tabby session ensure --profile xero`."
        )
    bearer = await get_bearer()
    tenant_id, shortcode = await get_tenant(ws_url, bearer)
    res = await _fetch(ws_url, bearer, tenant_id, shortcode, path)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        tenant_id, shortcode = await get_tenant(ws_url, bearer, force=True)
        res = await _fetch(ws_url, bearer, tenant_id, shortcode, path)

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero api.xro/2.0/{path} returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )
    return json.loads(res["body"]) if res.get("body") else {}

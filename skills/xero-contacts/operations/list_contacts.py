#!/usr/bin/env python3
"""Skill operation: list_contacts

Lists contacts for the authenticated Xero organisation, with an optional
name/email filter. Runs inside Tabby's authenticated browser via CDP using a
sniffed in-memory bearer token. See noui_runtime/xero_auth.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.cdp import cdp_eval, find_page  # noqa: E402
from noui_runtime.xero_account import get_tenant  # noqa: E402
from noui_runtime.xero_auth import get_bearer  # noqa: E402

API_BASE = "https://api.xero.com/api.xro/2.0"
PAGE_MATCH = "go.xero.com"
SHELL_APP = "Invoicing"


async def _fetch(ws_url: str, bearer: str, tenant_id: str, shortcode: str, page: int) -> dict:
    url = f"{API_BASE}/Contacts?page={page}"
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


async def execute(query: str = "", page: int = 1) -> dict:
    """List contacts for the authenticated Xero organisation.

    Args:
        query: Optional case-insensitive filter on name/email.
        page: 1-based page number.

    Returns:
        {count, page, contacts: [{id, name, email, status, is_customer, is_supplier}]}
    """
    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            "`tabby session ensure --profile xero` and open go.xero.com."
        )

    bearer = await get_bearer()
    tenant_id, shortcode = await get_tenant(ws_url, bearer)
    res = await _fetch(ws_url, bearer, tenant_id, shortcode, page)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        tenant_id, shortcode = await get_tenant(ws_url, bearer, force=True)
        res = await _fetch(ws_url, bearer, tenant_id, shortcode, page)

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero Contacts API returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    raw = ((json.loads(res["body"]) or {}).get("Contacts")) or []
    needle = query.strip().lower()
    contacts = []
    for c in raw:
        name = c.get("Name") or ""
        email = c.get("EmailAddress") or ""
        if needle and needle not in f"{name} {email}".lower():
            continue
        contacts.append(
            {
                "id": c.get("ContactID"),
                "name": name,
                "email": email,
                "status": c.get("ContactStatus"),
                "is_customer": c.get("IsCustomer"),
                "is_supplier": c.get("IsSupplier"),
            }
        )

    return {"count": len(contacts), "page": page, "contacts": contacts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_contacts",
        description="List contacts for the authenticated Xero organisation.",
    )
    parser.add_argument("--query", default="", help="Filter on name/email.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(query=args.query, page=args.page))
    except Exception as exc:
        print(f"list_contacts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

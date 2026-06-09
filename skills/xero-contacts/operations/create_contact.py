#!/usr/bin/env python3
"""Skill operation: create_contact

Creates a new contact in the authenticated Xero organisation. Runs inside Tabby's
authenticated browser via CDP using a sniffed in-memory bearer token.
See noui_runtime/xero_auth.py.

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


async def _api(
    ws_url: str,
    bearer: str,
    tenant_id: str,
    shortcode: str,
    method: str,
    path: str,
    body: dict | None = None,
) -> dict:
    url = f"{API_BASE}/{path}"
    headers = {
        "Authorization": bearer,
        "Accept": "application/json",
        "xero-tenant-id": tenant_id,
        "xero-tenant-shortcode": shortcode,
        "xero-shell-app-name": SHELL_APP,
        "xero-correlation-id": str(uuid.uuid4()),
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    init = {"method": method, "credentials": "omit", "headers": headers}
    if body is not None:
        init["body"] = json.dumps(body)
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)


async def execute(
    name: str,
    email: str = "",
    is_customer: bool = True,
    is_supplier: bool = False,
) -> dict:
    """Create a contact in Xero.

    Args:
        name: Contact or company name (required).
        email: Contact email.
        is_customer: Mark as a customer (default True).
        is_supplier: Mark as a supplier.

    Returns:
        {id, name, email, status, is_customer, is_supplier}
    """
    if not name.strip():
        raise ValueError("--name is required.")

    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            "`tabby session ensure --profile xero` and open go.xero.com."
        )

    bearer = await get_bearer()
    tenant_id, shortcode = await get_tenant(ws_url, bearer)

    payload: dict = {
        "Name": name.strip(),
        "IsCustomer": is_customer,
        "IsSupplier": is_supplier,
    }
    if email:
        payload["EmailAddress"] = email.strip()

    res = await _api(
        ws_url, bearer, tenant_id, shortcode, "POST", "Contacts", {"Contacts": [payload]}
    )
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        tenant_id, shortcode = await get_tenant(ws_url, bearer, force=True)
        res = await _api(
            ws_url, bearer, tenant_id, shortcode, "POST", "Contacts", {"Contacts": [payload]}
        )

    if res.get("status") not in (200, 201):
        raise RuntimeError(
            f"Xero create contact returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    c = (((json.loads(res["body"]) or {}).get("Contacts")) or [{}])[0]
    return {
        "id": c.get("ContactID"),
        "name": c.get("Name"),
        "email": c.get("EmailAddress"),
        "status": c.get("ContactStatus"),
        "is_customer": c.get("IsCustomer"),
        "is_supplier": c.get("IsSupplier"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_contact",
        description="Create a contact in the authenticated Xero organisation.",
    )
    parser.add_argument("--name", required=True, help="Contact or company name.")
    parser.add_argument("--email", default="", help="Contact email.")
    parser.add_argument(
        "--customer",
        dest="is_customer",
        action="store_true",
        default=True,
        help="Mark as a customer (default).",
    )
    parser.add_argument(
        "--supplier", dest="is_supplier", action="store_true", help="Mark as a supplier."
    )
    parser.add_argument(
        "--no-customer", dest="is_customer", action="store_false", help="Do not mark as customer."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                name=args.name,
                email=args.email,
                is_customer=args.is_customer,
                is_supplier=args.is_supplier,
            )
        )
    except Exception as exc:
        print(f"create_contact failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Skill operation: list_invoice_customers

Lists customers from the Xero Sales/Invoicing UI using the same BFF endpoint the
page calls: ``GET go.xero.com/api/invoicing/customer/find``. Runs inside Tabby's
authenticated browser through Tabby's POST /execute/fetch. See noui_runtime/xero_invoicing.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.xero_invoicing import get_invoicing_headers, invoicing_fetch  # noqa: E402


async def execute(query: str = "", page: int = 1) -> dict:
    """List customers available when creating invoices in Xero Sales.

    Args:
        query: Optional search string (same as the invoicing customer picker).
        page: 1-based page number.

    Returns:
        {count, page, customers: [{id, name, email}]}
    """
    headers = await get_invoicing_headers()
    q = urllib.parse.urlencode({"page": page, "q": query})
    res = await invoicing_fetch(f"customer/find?{q}", headers=headers)
    if res.get("status") in (401, 403):
        headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(f"customer/find?{q}", headers=headers)

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero customer/find returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    raw = json.loads(res["body"]) if res.get("body") else []
    customers = [
        {
            "id": c.get("Id"),
            "name": c.get("Name"),
            "email": c.get("Email"),
        }
        for c in raw
    ]
    return {"count": len(customers), "page": page, "customers": customers}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_invoice_customers",
        description="List customers from the Xero Sales/Invoicing customer picker API.",
    )
    parser.add_argument("--query", default="", help="Search string.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(query=args.query, page=args.page))
    except Exception as exc:
        print(f"list_invoice_customers failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

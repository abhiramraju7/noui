#!/usr/bin/env python3
"""Skill operation: list_sales_accounts

Lists sales/revenue accounts from the Xero Sales/Invoicing UI using
``GET go.xero.com/api/invoicing/account`` — the same call the invoicing page
makes on load.

Prints JSON on stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.xero_invoicing import get_invoicing_headers, invoicing_fetch  # noqa: E402


async def execute() -> dict:
    """List sales accounts available on invoice line items."""
    ws_url, headers = await get_invoicing_headers()
    res = await invoicing_fetch(ws_url, headers, "account")
    if res.get("status") in (401, 403):
        ws_url, headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(ws_url, headers, "account")

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero account returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    raw = json.loads(res["body"]) if res.get("body") else []
    accounts = [
        {
            "id": a.get("Id"),
            "code": a.get("Code"),
            "name": a.get("Name"),
            "type": a.get("Type"),
            "tax_type": a.get("TaxType"),
        }
        for a in raw
    ]
    return {"count": len(accounts), "accounts": accounts}


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_sales_accounts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

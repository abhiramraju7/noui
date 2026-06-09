#!/usr/bin/env python3
"""Skill operation: list_tax_rates

Lists tax rates from the Xero Sales/Invoicing UI using
``GET go.xero.com/api/invoicing/taxRateAce`` — the same call the invoicing page
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
    """List tax rates available when creating invoices."""
    ws_url, headers = await get_invoicing_headers()
    res = await invoicing_fetch(ws_url, headers, "taxRateAce")
    if res.get("status") in (401, 403):
        ws_url, headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(ws_url, headers, "taxRateAce")

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero taxRateAce returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    raw = json.loads(res["body"]) if res.get("body") else []
    rates = [
        {
            "name": r.get("Name"),
            "tax_type": r.get("TaxType"),
            "rate": (r.get("TaxComponents") or [{}])[0].get("Rate"),
        }
        for r in raw
    ]
    return {"count": len(rates), "tax_rates": rates}


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_tax_rates failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

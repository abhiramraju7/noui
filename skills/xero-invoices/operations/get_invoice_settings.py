#!/usr/bin/env python3
"""Skill operation: get_invoice_settings

Fetches org invoice settings from the Xero Sales/Invoicing UI using
``GET go.xero.com/api/invoicing/appData`` — the same call the invoicing page
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
    """Return invoice settings for the authenticated Xero organisation."""
    ws_url, headers = await get_invoicing_headers()
    res = await invoicing_fetch(ws_url, headers, "appData")
    if res.get("status") in (401, 403):
        ws_url, headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(ws_url, headers, "appData")

    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero appData returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    data = json.loads(res["body"]) if res.get("body") else {}
    return {
        "base_currency": data.get("BaseCurrency"),
        "country_code": data.get("CountryCode"),
        "default_tax_basis": data.get("DefaultTaxBasis"),
        "auto_tax_status": data.get("AutoTaxStatus"),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"get_invoice_settings failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

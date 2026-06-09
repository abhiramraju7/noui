#!/usr/bin/env python3
"""Skill operation: list_purchase_orders

Lists purchase orders from the Xero accounting API
(``GET api.xro/2.0/PurchaseOrders``): number, supplier, status, total, and date.

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

from noui_runtime.xero_api import xro_get  # noqa: E402


async def execute() -> dict:
    """List purchase orders for the authenticated Xero org."""
    data = await xro_get("PurchaseOrders")
    raw = data.get("PurchaseOrders") or []
    orders = []
    for p in raw:
        contact = p.get("Contact") or {}
        orders.append(
            {
                "id": p.get("PurchaseOrderID"),
                "number": p.get("PurchaseOrderNumber"),
                "supplier": contact.get("Name"),
                "status": p.get("Status"),
                "total": p.get("Total"),
                "currency": p.get("CurrencyCode"),
                "date": p.get("DateString") or p.get("Date"),
            }
        )
    return {"count": len(orders), "purchase_orders": orders}


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_purchase_orders failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

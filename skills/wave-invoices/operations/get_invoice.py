#!/usr/bin/env python3
"""Skill operation: get_invoice — fetch one Wave invoice by id."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.wave_gql import get_business_id, gql_request  # noqa: E402

_QUERY = """
query ($businessId: ID!, $invoiceId: ID!) {
  business(id: $businessId) {
    invoice(id: $invoiceId) {
      id
      invoiceNumber
      status
      invoiceDate
      dueDate
      total { value }
      amountDue { value }
      amountPaid { value }
      currency { code }
      customer { id name email }
      items {
        description
        quantity
        price
        total { value }
        product { id name }
      }
    }
  }
}
"""


async def execute(invoice_id: str) -> dict:
    business_id = await get_business_id()
    body = await gql_request(_QUERY, {"businessId": business_id, "invoiceId": invoice_id})
    inv = ((body.get("data") or {}).get("business") or {}).get("invoice") or {}
    return {
        "id": inv.get("id"),
        "number": inv.get("invoiceNumber"),
        "customer": (inv.get("customer") or {}).get("name"),
        "status": inv.get("status"),
        "total": (inv.get("total") or {}).get("value"),
        "balance": (inv.get("amountDue") or {}).get("value"),
        "paid": (inv.get("amountPaid") or {}).get("value"),
        "currency": (inv.get("currency") or {}).get("code"),
        "date": inv.get("invoiceDate"),
        "due_date": inv.get("dueDate"),
        "line_items": [
            {
                "description": li.get("description"),
                "quantity": li.get("quantity"),
                "price": li.get("price"),
                "total": (li.get("total") or {}).get("value"),
                "product": (li.get("product") or {}).get("name"),
            }
            for li in (inv.get("items") or [])
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="get_invoice")
    parser.add_argument("--invoice-id", dest="invoice_id", required=True)
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(execute(invoice_id=args.invoice_id))
    except Exception as exc:
        print(f"get_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

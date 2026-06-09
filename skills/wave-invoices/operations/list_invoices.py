#!/usr/bin/env python3
"""Skill operation: list_invoices — list Wave invoices for the open business."""

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
query ($businessId: ID!, $page: Int!, $pageSize: Int!, $customerId: ID) {
  business(id: $businessId) {
    invoices(page: $page, pageSize: $pageSize, customerId: $customerId) {
      edges {
        node {
          id
          invoiceNumber
          status
          invoiceDate
          dueDate
          total { value }
          amountDue { value }
          amountPaid { value }
          currency { code }
          customer { id name }
        }
      }
    }
  }
}
"""


async def execute(customer_id: str = "", page: int = 1, page_size: int = 50) -> dict:
    business_id = await get_business_id()
    variables: dict = {
        "businessId": business_id,
        "page": page,
        "pageSize": page_size,
        "customerId": customer_id or None,
    }
    body = await gql_request(_QUERY, variables)
    edges = (
        (((body.get("data") or {}).get("business") or {}).get("invoices") or {}).get("edges")
    ) or []
    invoices = [
        {
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
        }
        for inv in (e.get("node") or {} for e in edges)
    ]
    return {"count": len(invoices), "page": page, "invoices": invoices}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="list_invoices")
    p.add_argument("--customer-id", default="", help="Filter by customer GraphQL id.")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(customer_id=args.customer_id, page=args.page, page_size=args.page_size)
        )
    except Exception as exc:
        print(f"list_invoices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

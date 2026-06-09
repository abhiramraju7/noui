#!/usr/bin/env python3
"""Skill operation: list_invoices

List invoices for the authenticated Zoho Books org, with an optional status
filter. Read-only. Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.zoho_books import books_request  # noqa: E402

_STATUS_FILTERS = {
    "draft": "Status.Draft",
    "sent": "Status.Sent",
    "overdue": "Status.OverDue",
    "paid": "Status.Paid",
    "unpaid": "Status.Unpaid",
    "all": "Status.All",
}


async def execute(status: str = "", page: int = 1) -> dict:
    """List invoices.

    Args:
        status: Optional filter: draft, sent, overdue, paid, unpaid, all.
        page: 1-based page number.

    Returns:
        {count, page, invoices: [{id, number, customer, status, total, balance, currency, date, due_date}]}
    """
    params: dict = {"page": page, "per_page": 200}
    if status:
        key = status.strip().lower()
        if key not in _STATUS_FILTERS:
            raise ValueError(f"Unknown status {status!r}. Choose from {sorted(_STATUS_FILTERS)}.")
        params["filter_by"] = _STATUS_FILTERS[key]
    res = await books_request("invoices", params=params)
    if res["status"] != 200:
        raise RuntimeError(f"invoices API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("invoices") or []
    invoices = [
        {
            "id": inv.get("invoice_id"),
            "number": inv.get("invoice_number"),
            "customer": inv.get("customer_name"),
            "status": inv.get("status"),
            "total": inv.get("total"),
            "balance": inv.get("balance"),
            "currency": inv.get("currency_code"),
            "date": inv.get("date"),
            "due_date": inv.get("due_date"),
        }
        for inv in raw
    ]
    return {"count": len(invoices), "page": page, "invoices": invoices}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="list_invoices", description="List Zoho Books invoices.")
    parser.add_argument("--status", default="", help="draft|sent|overdue|paid|unpaid|all")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(status=args.status, page=args.page))
    except Exception as exc:
        print(f"list_invoices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

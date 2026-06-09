#!/usr/bin/env python3
"""Skill operation: get_invoice

Fetch a single invoice by id, including line items and payment status.
Read-only. Prints JSON on stdout.
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


async def execute(invoice_id: str) -> dict:
    """Return full detail for one invoice."""
    res = await books_request(f"invoices/{invoice_id}")
    if res["status"] != 200:
        raise RuntimeError(f"invoices/{invoice_id} returned {res['status']}: {str(res['body'])[:300]}")
    inv = (res["body"] or {}).get("invoice") or {}
    return {
        "id": inv.get("invoice_id"),
        "number": inv.get("invoice_number"),
        "customer": inv.get("customer_name"),
        "status": inv.get("status"),
        "total": inv.get("total"),
        "balance": inv.get("balance"),
        "currency": inv.get("currency_code"),
        "date": inv.get("date"),
        "due_date": inv.get("due_date"),
        "line_items": [
            {"name": li.get("name"), "quantity": li.get("quantity"), "rate": li.get("rate"), "total": li.get("item_total")}
            for li in (inv.get("line_items") or [])
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="get_invoice", description="Get one Zoho Books invoice.")
    parser.add_argument("--invoice-id", dest="invoice_id", required=True, help="Invoice id.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(invoice_id=args.invoice_id))
    except Exception as exc:
        print(f"get_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

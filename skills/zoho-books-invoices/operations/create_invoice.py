#!/usr/bin/env python3
"""Skill operation: create_invoice

Create an invoice in the authenticated Zoho Books org for a customer (resolved
by name), with a single line item. Created as a draft; pass --send to also email
it (which marks it Sent). Writes data. Prints JSON on stdout.
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
from noui_runtime.zoho_resolve import resolve_customer  # noqa: E402


async def execute(
    customer: str,
    description: str,
    quantity: float = 1.0,
    rate: float = 0.0,
    invoice_date: str = "",
    due_date: str = "",
    send: bool = False,
) -> dict:
    """Create an invoice with one line item.

    Args:
        customer: Customer name or contact_id (resolved via the contacts API).
        description: Line item name/description.
        quantity: Line item quantity.
        rate: Line item unit price.
        invoice_date: YYYY-MM-DD (defaults to Zoho's today).
        due_date: YYYY-MM-DD.
        send: When true, email the invoice after creating it (marks it Sent).

    Returns:
        {id, number, customer, status, total, balance, currency}
    """
    cust = await resolve_customer(customer)
    payload: dict = {
        "customer_id": cust["contact_id"],
        "line_items": [
            {
                "name": description[:100],
                "description": description,
                "rate": rate,
                "quantity": quantity,
            }
        ],
    }
    if invoice_date:
        payload["date"] = invoice_date
    if due_date:
        payload["due_date"] = due_date

    res = await books_request("invoices", method="POST", body=payload)
    body = res["body"] or {}
    if res["status"] not in (200, 201) or body.get("code") not in (0, None):
        raise RuntimeError(f"create_invoice failed ({res['status']}): {str(body)[:300]}")
    inv = body.get("invoice") or {}
    invoice_id = inv.get("invoice_id")

    emailed = False
    if send and invoice_id:
        em = await books_request(f"invoices/{invoice_id}/status/sent", method="POST")
        emailed = em["status"] == 200 and (em["body"] or {}).get("code") in (0, None)

    return {
        "id": invoice_id,
        "number": inv.get("invoice_number"),
        "customer": inv.get("customer_name"),
        "status": "sent" if emailed else inv.get("status"),
        "total": inv.get("total"),
        "balance": inv.get("balance"),
        "currency": inv.get("currency_code"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_invoice", description="Create a Zoho Books invoice."
    )
    parser.add_argument("--customer", required=True, help="Customer name or contact_id.")
    parser.add_argument("--description", required=True, help="Line item description.")
    parser.add_argument("--quantity", type=float, default=1.0, help="Line item quantity.")
    parser.add_argument("--rate", type=float, default=0.0, help="Line item unit price.")
    parser.add_argument("--date", dest="invoice_date", default="", help="Invoice date YYYY-MM-DD.")
    parser.add_argument("--due-date", dest="due_date", default="", help="Due date YYYY-MM-DD.")
    parser.add_argument(
        "--send", action="store_true", help="Mark the invoice as Sent after creating."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                customer=args.customer,
                description=args.description,
                quantity=args.quantity,
                rate=args.rate,
                invoice_date=args.invoice_date,
                due_date=args.due_date,
                send=args.send,
            )
        )
    except Exception as exc:
        print(f"create_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

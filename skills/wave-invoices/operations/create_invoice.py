#!/usr/bin/env python3
"""Skill operation: create_invoice — create a Wave invoice with one line item."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.wave_gql import get_business_id, gql_input_errors, gql_request  # noqa: E402
from noui_runtime.wave_resolve import resolve_customer, resolve_or_create_product  # noqa: E402

_MUTATION = """
mutation ($input: InvoiceCreateInput!) {
  invoiceCreate(input: $input) {
    didSucceed
    inputErrors { message path code }
    invoice {
      id
      invoiceNumber
      status
      total { value }
      amountDue { value }
      currency { code }
      customer { name }
    }
  }
}
"""


async def execute(
    customer: str,
    description: str,
    quantity: float = 1.0,
    unit_price: float = 0.0,
    invoice_date: str = "",
    due_date: str = "",
    send: bool = False,
) -> dict:
    business_id = await get_business_id()
    cust = await resolve_customer(customer)
    product_id = await resolve_or_create_product(description, unit_price)
    inp: dict = {
        "businessId": business_id,
        "customerId": cust["id"],
        "invoiceDate": invoice_date or date.today().isoformat(),
        "items": [
            {
                "productId": product_id,
                "description": description,
                "quantity": quantity,
                "price": unit_price,
            }
        ],
    }
    if due_date:
        inp["dueDate"] = due_date

    body = await gql_request(_MUTATION, {"input": inp})
    gql_input_errors(body, "invoiceCreate")
    inv = ((body.get("data") or {}).get("invoiceCreate") or {}).get("invoice") or {}
    invoice_id = inv.get("id")

    if send and invoice_id:
        send_body = await gql_request(
            """
            mutation ($input: InvoiceSendInput!) {
              invoiceSend(input: $input) {
                didSucceed
                inputErrors { message path }
                invoice { id status }
              }
            }
            """,
            {
                "input": {
                    "invoiceId": invoice_id,
                    "to": [cust["email"]] if cust.get("email") else [],
                    "attachPDF": True,
                }
            },
        )
        sent = ((send_body.get("data") or {}).get("invoiceSend") or {}).get("invoice") or {}
        if sent.get("status"):
            inv["status"] = sent["status"]

    return {
        "id": invoice_id,
        "number": inv.get("invoiceNumber"),
        "customer": (inv.get("customer") or {}).get("name") or cust.get("name"),
        "status": inv.get("status"),
        "total": (inv.get("total") or {}).get("value"),
        "balance": (inv.get("amountDue") or {}).get("value"),
        "currency": (inv.get("currency") or {}).get("code"),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="create_invoice")
    p.add_argument("--customer", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--quantity", type=float, default=1.0)
    p.add_argument("--unit-price", type=float, default=0.0)
    p.add_argument("--date", dest="invoice_date", default="")
    p.add_argument("--due-date", dest="due_date", default="")
    p.add_argument("--send", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                customer=args.customer,
                description=args.description,
                quantity=args.quantity,
                unit_price=args.unit_price,
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

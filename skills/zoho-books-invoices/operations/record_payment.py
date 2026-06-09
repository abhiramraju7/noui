#!/usr/bin/env python3
"""Skill operation: record_payment

Record a customer payment against an invoice (marks it Paid when fully applied).
Resolves the deposit account by name/id. Writes data. Prints JSON on stdout.
"""

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

from noui_runtime.zoho_books import books_request  # noqa: E402
from noui_runtime.zoho_resolve import resolve_account  # noqa: E402


async def execute(
    invoice_id: str,
    amount: float,
    account: str,
    payment_date: str = "",
    payment_mode: str = "cash",
    reference: str = "",
) -> dict:
    """Record a payment against an invoice.

    Args:
        invoice_id: Invoice to pay (must not be a draft).
        amount: Payment amount applied to the invoice.
        account: Deposit account name or id (resolved via bank accounts).
        payment_date: YYYY-MM-DD (defaults to today).
        payment_mode: cash, banktransfer, check, creditcard, etc.
        reference: Optional reference number.

    Returns:
        {payment_id, invoice_id, amount, account, mode, date}
    """
    # Resolve the customer for this invoice (required by the payments API).
    inv = await books_request(f"invoices/{invoice_id}")
    if inv["status"] != 200:
        raise RuntimeError(f"Could not load invoice {invoice_id}: {str(inv['body'])[:200]}")
    invoice = (inv["body"] or {}).get("invoice") or {}
    customer_id = invoice.get("customer_id")

    acct = await resolve_account(account)
    payload: dict = {
        "customer_id": customer_id,
        "payment_mode": payment_mode,
        "amount": amount,
        "date": payment_date or date.today().isoformat(),
        "account_id": acct["account_id"],
        "invoices": [{"invoice_id": invoice_id, "amount_applied": amount}],
    }
    if reference:
        payload["reference_number"] = reference

    res = await books_request("customerpayments", method="POST", body=payload)
    body = res["body"] or {}
    if res["status"] not in (200, 201) or body.get("code") not in (0, None):
        raise RuntimeError(f"record_payment failed ({res['status']}): {str(body)[:300]}")
    pay = body.get("payment") or {}
    return {
        "payment_id": pay.get("payment_id"),
        "invoice_id": invoice_id,
        "amount": pay.get("amount", amount),
        "account": acct["account_name"],
        "mode": pay.get("payment_mode", payment_mode),
        "date": pay.get("date", payload["date"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="record_payment", description="Record a Zoho Books invoice payment.")
    parser.add_argument("--invoice-id", dest="invoice_id", required=True, help="Invoice id.")
    parser.add_argument("--amount", type=float, required=True, help="Payment amount.")
    parser.add_argument("--account", required=True, help="Deposit account name or id.")
    parser.add_argument("--date", dest="payment_date", default="", help="Payment date YYYY-MM-DD.")
    parser.add_argument("--mode", dest="payment_mode", default="cash", help="Payment mode (cash, banktransfer, check...).")
    parser.add_argument("--reference", default="", help="Reference number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice_id=args.invoice_id, amount=args.amount, account=args.account,
                payment_date=args.payment_date, payment_mode=args.payment_mode, reference=args.reference,
            )
        )
    except Exception as exc:
        print(f"record_payment failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

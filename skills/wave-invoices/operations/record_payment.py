#!/usr/bin/env python3
"""Skill operation: record_payment — record a manual payment against a Wave invoice."""

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
from noui_runtime.wave_resolve import resolve_payment_account  # noqa: E402

_MUTATION = """
mutation ($input: InvoicePaymentCreateManualInput!) {
  invoicePaymentCreateManual(input: $input) {
    didSucceed
    inputErrors { message path code }
    invoicePayment { id amount paymentDate paymentMethod }
  }
}
"""


async def execute(
    invoice_id: str,
    amount: float,
    account: str,
    payment_date: str = "",
    payment_method: str = "CASH",
) -> dict:
    business_id = await get_business_id()
    acct = await resolve_payment_account(account)
    body = await gql_request(
        _MUTATION,
        {
            "input": {
                "businessId": business_id,
                "invoiceId": invoice_id,
                "paymentAccountId": acct["id"],
                "amount": amount,
                "paymentDate": payment_date or date.today().isoformat(),
                "paymentMethod": payment_method,
                "exchangeRate": 1.0,
            }
        },
    )
    gql_input_errors(body, "invoicePaymentCreateManual")
    pay = (
        ((body.get("data") or {}).get("invoicePaymentCreateManual") or {}).get("invoicePayment")
    ) or {}
    return {
        "payment_id": pay.get("id"),
        "invoice_id": invoice_id,
        "amount": pay.get("amount", amount),
        "account": acct["name"],
        "method": pay.get("paymentMethod", payment_method),
        "date": pay.get("paymentDate", payment_date or date.today().isoformat()),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="record_payment")
    p.add_argument("--invoice-id", required=True)
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--account", required=True, help="Payment account name or id.")
    p.add_argument("--date", dest="payment_date", default="")
    p.add_argument("--method", dest="payment_method", default="CASH")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice_id=args.invoice_id,
                amount=args.amount,
                account=args.account,
                payment_date=args.payment_date,
                payment_method=args.payment_method,
            )
        )
    except Exception as exc:
        print(f"record_payment failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

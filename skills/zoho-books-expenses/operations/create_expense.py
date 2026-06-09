#!/usr/bin/env python3
"""Skill operation: create_expense

Record an expense in the authenticated Zoho Books org under an expense account,
paid through a bank/cash account, optionally tied to a vendor. Writes data.
Prints JSON on stdout.
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
from noui_runtime.zoho_resolve import (  # noqa: E402
    resolve_account_by_type,
    resolve_paid_through,
    resolve_vendor,
)


async def execute(
    account: str,
    amount: float,
    paid_through: str = "Petty Cash",
    vendor: str = "",
    expense_date: str = "",
    description: str = "",
    reference: str = "",
) -> dict:
    """Record an expense.

    Args:
        account: Expense account name or id (resolved via chart of accounts).
        amount: Expense amount.
        paid_through: Bank/cash account the expense was paid from.
        vendor: Optional vendor name or contact_id.
        expense_date: YYYY-MM-DD (defaults to today).
        description: Optional note.
        reference: Optional reference number.

    Returns:
        {id, account, paid_through, amount, date, status}
    """
    acct = await resolve_account_by_type(account, account_type="expense")
    paid = await resolve_paid_through(paid_through)
    vendor_id = await resolve_vendor(vendor)

    payload: dict = {
        "account_id": acct["account_id"],
        "paid_through_account_id": paid["account_id"],
        "amount": amount,
        "date": expense_date or date.today().isoformat(),
    }
    if vendor_id:
        payload["vendor_id"] = vendor_id
    if description:
        payload["description"] = description
    if reference:
        payload["reference_number"] = reference

    res = await books_request("expenses", method="POST", body=payload)
    body = res["body"] or {}
    if res["status"] not in (200, 201) or body.get("code") not in (0, None):
        raise RuntimeError(f"create_expense failed ({res['status']}): {str(body)[:300]}")
    e = body.get("expense") or {}
    return {
        "id": e.get("expense_id"),
        "account": e.get("account_name", acct["account_name"]),
        "paid_through": e.get("paid_through_account_name", paid["account_name"]),
        "amount": e.get("total", amount),
        "date": e.get("date", payload["date"]),
        "status": e.get("status"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_expense", description="Record a Zoho Books expense."
    )
    parser.add_argument("--account", required=True, help="Expense account name or id.")
    parser.add_argument("--amount", type=float, required=True, help="Expense amount.")
    parser.add_argument(
        "--paid-through",
        dest="paid_through",
        default="Petty Cash",
        help="Bank/cash account paid from.",
    )
    parser.add_argument("--vendor", default="", help="Vendor name or contact_id.")
    parser.add_argument("--date", dest="expense_date", default="", help="Expense date YYYY-MM-DD.")
    parser.add_argument("--description", default="", help="Note.")
    parser.add_argument("--reference", default="", help="Reference number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                account=args.account,
                amount=args.amount,
                paid_through=args.paid_through,
                vendor=args.vendor,
                expense_date=args.expense_date,
                description=args.description,
                reference=args.reference,
            )
        )
    except Exception as exc:
        print(f"create_expense failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

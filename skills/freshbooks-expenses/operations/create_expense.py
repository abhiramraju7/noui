#!/usr/bin/env python3
"""Skill operation: create_expense

Records a new expense in the authenticated FreshBooks account. The category is given
by name and resolved to a FreshBooks category id; the staff id (expense owner) is
resolved automatically to the account owner. Runs through Tabby's POST /execute/fetch,
i.e. fetch() inside the authenticated FreshBooks browser session.
See noui_runtime/freshbooks_api.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


async def _api(account_id: str, method: str, path: str, body: dict | None = None) -> dict:
    return await fb_request(
        f"/accounting/account/{account_id}/{path}",
        method=method,
        account_id=account_id,
        body=body,
    )


async def _resolve_category(account_id: str, category: str) -> tuple[int, str]:
    data = await _api(account_id, "GET", "expenses/categories?per_page=200")
    cats = (((data or {}).get("response") or {}).get("result") or {}).get("categories", [])
    needle = category.strip().lower()
    exact = [c for c in cats if (c.get("category") or "").strip().lower() == needle]
    matches = exact or [c for c in cats if needle in (c.get("category") or "").lower()]
    if not matches:
        sample = ", ".join(sorted((c.get("category") or "") for c in cats)[:25])
        raise ValueError(f"No expense category matching {category!r}. Examples: {sample} ...")
    if len(matches) > 1 and not exact:
        labels = ", ".join((c.get("category") or "") for c in matches[:10])
        raise ValueError(f"Category {category!r} is ambiguous; matches: {labels}")
    chosen = (exact or matches)[0]
    return chosen.get("categoryid"), chosen.get("category")


async def _resolve_staff_id(account_id: str) -> int:
    data = await _api(account_id, "GET", "users/staffs?per_page=10")
    result = ((data or {}).get("response") or {}).get("result") or {}
    staff = result.get("staff") or result.get("staffs") or []
    if not staff:
        raise RuntimeError("No staff found for this account; cannot set expense owner.")
    return staff[0].get("id")


async def execute(
    amount: float,
    category: str,
    vendor: str = "",
    date: str | None = None,
    currency_code: str = "USD",
    notes: str = "",
) -> dict:
    """Record an expense in FreshBooks.

    Args:
        amount: Expense amount.
        category: Expense category name (e.g. "Advertising"), resolved to a category id.
        vendor: Vendor/merchant name.
        date: Expense date YYYY-MM-DD (defaults to today).
        currency_code: ISO currency code (default USD).
        notes: Free-text note.

    Returns:
        {id, vendor, amount, currency, category, date, notes}
    """
    if amount is None:
        raise ValueError("--amount is required.")
    date = date or _dt.date.today().isoformat()

    account_id = await get_account_id()
    category_id, category_name = await _resolve_category(account_id, category)
    staff_id = await _resolve_staff_id(account_id)

    body = {
        "expense": {
            "amount": {"amount": f"{float(amount):.2f}", "code": currency_code},
            "categoryid": category_id,
            "staffid": staff_id,
            "date": date,
            "vendor": vendor,
            "notes": notes,
        }
    }

    data = await _api(account_id, "POST", "expenses/expenses", body)
    e = (((data or {}).get("response") or {}).get("result") or {}).get("expense", {})
    amt = e.get("amount") or {}
    return {
        "id": e.get("id"),
        "vendor": e.get("vendor"),
        "amount": amt.get("amount"),
        "currency": amt.get("code"),
        "category": category_name,
        "date": e.get("date"),
        "notes": e.get("notes"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_expense",
        description="Record an expense in the authenticated FreshBooks account.",
    )
    parser.add_argument("--amount", type=float, required=True, help="Expense amount.")
    parser.add_argument(
        "--category", required=True, help="Expense category name, e.g. 'Advertising'."
    )
    parser.add_argument("--vendor", default="", help="Vendor/merchant name.")
    parser.add_argument("--date", default=None, help="Expense date YYYY-MM-DD (default today).")
    parser.add_argument(
        "--currency-code", dest="currency_code", default="USD", help="ISO currency code."
    )
    parser.add_argument("--notes", default="", help="Free-text note.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                amount=args.amount,
                category=args.category,
                vendor=args.vendor,
                date=args.date,
                currency_code=args.currency_code,
                notes=args.notes,
            )
        )
    except Exception as exc:
        print(f"create_expense failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

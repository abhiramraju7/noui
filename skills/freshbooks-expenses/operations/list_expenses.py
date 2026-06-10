#!/usr/bin/env python3
"""Skill operation: list_expenses

Lists expenses for the authenticated FreshBooks account. Runs through Tabby's
POST /execute/fetch, i.e. fetch() inside the authenticated FreshBooks browser
session. See noui_runtime/freshbooks_api.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


async def _fetch_categories(account_id: str) -> dict:
    try:
        data = await fb_request(
            f"/accounting/account/{account_id}/expenses/categories?per_page=200",
            account_id=account_id,
        )
    except RuntimeError:
        return {}
    cats = (((data or {}).get("response") or {}).get("result") or {}).get("categories", [])
    return {c.get("categoryid"): c.get("category") for c in cats}


async def _fetch(account_id: str, page: int, per_page: int) -> dict:
    query = urllib.parse.urlencode({"page": page, "per_page": per_page})
    path = f"/accounting/account/{account_id}/expenses/expenses?{query}"
    return await fb_request(path, account_id=account_id)


async def execute(page: int = 1, per_page: int = 50) -> dict:
    """List expenses for the authenticated FreshBooks account.

    Returns:
        {count, page, per_page, total, expenses: [{id, vendor, amount, currency,
         category, date, notes}]}
    """
    account_id = await get_account_id()
    data = await _fetch(account_id, page, per_page)
    result = ((data or {}).get("response") or {}).get("result") or {}
    raw = result.get("expenses", [])
    cat_names = await _fetch_categories(account_id) if raw else {}

    expenses = []
    for e in raw:
        amount = e.get("amount") or {}
        expenses.append(
            {
                "id": e.get("id"),
                "vendor": e.get("vendor"),
                "amount": amount.get("amount"),
                "currency": amount.get("code"),
                "category": cat_names.get(e.get("categoryid")),
                "date": e.get("date"),
                "notes": e.get("notes"),
            }
        )

    return {
        "count": len(expenses),
        "page": result.get("page", page),
        "per_page": result.get("per_page", per_page),
        "total": result.get("total"),
        "expenses": expenses,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_expenses",
        description="List expenses for the authenticated FreshBooks account.",
    )
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    parser.add_argument(
        "--per-page", dest="per_page", type=int, default=50, help="Expenses per page."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(page=args.page, per_page=args.per_page))
    except Exception as exc:
        print(f"list_expenses failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

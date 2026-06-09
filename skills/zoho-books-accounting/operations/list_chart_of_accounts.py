#!/usr/bin/env python3
"""Skill operation: list_chart_of_accounts

List chart-of-accounts entries (code, name, type) for the authenticated Zoho
Books org, with an optional account-type filter. Read-only. Prints JSON.
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


async def execute(account_type: str = "") -> dict:
    """List chart of accounts. Optional client-side filter by account_type substring
    (e.g. income, expense, bank, other_expense)."""
    res = await books_request("chartofaccounts")
    if res["status"] != 200:
        raise RuntimeError(f"chartofaccounts API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("chartofaccounts") or []
    if account_type:
        needle = account_type.strip().lower()
        raw = [a for a in raw if needle in (a.get("account_type") or "").lower()]
    accounts = [
        {
            "id": a.get("account_id"),
            "code": a.get("account_code"),
            "name": a.get("account_name"),
            "type": a.get("account_type"),
            "is_active": a.get("is_active"),
        }
        for a in raw
    ]
    return {"count": len(accounts), "accounts": accounts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="list_chart_of_accounts", description="List Zoho Books accounts.")
    parser.add_argument("--type", dest="account_type", default="", help="Account type filter, e.g. income/expense/bank.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(account_type=args.account_type))
    except Exception as exc:
        print(f"list_chart_of_accounts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

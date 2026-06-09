#!/usr/bin/env python3
"""Skill operation: list_expenses

List expenses for the authenticated Zoho Books org. Read-only. Prints JSON.
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


async def execute(page: int = 1) -> dict:
    """List expenses (id, date, account, vendor, total, status, currency)."""
    res = await books_request("expenses", params={"page": page, "per_page": 200})
    if res["status"] != 200:
        raise RuntimeError(f"expenses API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("expenses") or []
    expenses = [
        {
            "id": e.get("expense_id"),
            "date": e.get("date"),
            "account": e.get("account_name"),
            "vendor": e.get("vendor_name"),
            "total": e.get("total"),
            "currency": e.get("currency_code"),
            "status": e.get("status"),
            "description": e.get("description"),
        }
        for e in raw
    ]
    return {"count": len(expenses), "page": page, "expenses": expenses}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="list_expenses", description="List Zoho Books expenses.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(page=args.page))
    except Exception as exc:
        print(f"list_expenses failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

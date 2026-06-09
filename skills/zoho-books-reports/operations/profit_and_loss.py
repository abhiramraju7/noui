#!/usr/bin/env python3
"""Skill operation: profit_and_loss

Pull the Profit & Loss report for a date range from the authenticated Zoho Books
org. Read-only. Prints JSON on stdout.
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


def _flatten(sections: list, out: list, depth: int = 0) -> None:
    for s in sections or []:
        name = s.get("name") or s.get("account_name")
        total = s.get("total")
        if name is not None:
            out.append({"name": name, "total": total, "depth": depth})
        for key in ("account_transactions", "sub_sections", "sections", "transactions"):
            if isinstance(s.get(key), list):
                _flatten(s[key], out, depth + 1)


async def execute(from_date: str, to_date: str = "") -> dict:
    """Profit & Loss for [from_date, to_date].

    Args:
        from_date: Start date YYYY-MM-DD (required).
        to_date: End date YYYY-MM-DD (defaults to today).
    """
    params = {"from_date": from_date, "to_date": to_date or date.today().isoformat()}
    res = await books_request("reports/profitandloss", params=params)
    if res["status"] != 200:
        raise RuntimeError(f"profitandloss API returned {res['status']}: {str(res['body'])[:300]}")
    body = res["body"] or {}
    pnl = body.get("profit_and_loss") or body.get("profitandloss") or []
    rows: list = []
    _flatten(pnl if isinstance(pnl, list) else [pnl], rows)
    return {
        "from_date": params["from_date"],
        "to_date": params["to_date"],
        "rows": rows,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profit_and_loss", description="Zoho Books P&L report.")
    parser.add_argument(
        "--from-date", dest="from_date", required=True, help="Start date YYYY-MM-DD."
    )
    parser.add_argument(
        "--to-date", dest="to_date", default="", help="End date YYYY-MM-DD (default today)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(from_date=args.from_date, to_date=args.to_date))
    except Exception as exc:
        print(f"profit_and_loss failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

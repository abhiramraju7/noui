#!/usr/bin/env python3
"""Skill operation: balance_sheet

Pull the Balance Sheet report as of a date from the authenticated Zoho Books
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
        for key in ("account_transactions", "sub_sections", "sections", "transactions", "accounts"):
            if isinstance(s.get(key), list):
                _flatten(s[key], out, depth + 1)


async def execute(to_date: str = "", from_date: str = "") -> dict:
    """Balance Sheet as of to_date.

    Args:
        to_date: As-of date YYYY-MM-DD (defaults to today).
        from_date: Optional period start YYYY-MM-DD.
    """
    params: dict = {"to_date": to_date or date.today().isoformat()}
    if from_date:
        params["from_date"] = from_date
    res = await books_request("reports/balancesheet", params=params)
    if res["status"] != 200:
        raise RuntimeError(f"balancesheet API returned {res['status']}: {str(res['body'])[:300]}")
    body = res["body"] or {}
    bs = body.get("balance_sheet") or body.get("balancesheet") or []
    rows: list = []
    _flatten(bs if isinstance(bs, list) else [bs], rows)
    return {"to_date": params["to_date"], "rows": rows}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="balance_sheet", description="Zoho Books balance sheet report."
    )
    parser.add_argument(
        "--to-date", dest="to_date", default="", help="As-of date YYYY-MM-DD (default today)."
    )
    parser.add_argument(
        "--from-date", dest="from_date", default="", help="Optional period start YYYY-MM-DD."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(to_date=args.to_date, from_date=args.from_date))
    except Exception as exc:
        print(f"balance_sheet failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

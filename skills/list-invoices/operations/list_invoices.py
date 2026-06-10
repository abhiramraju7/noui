#!/usr/bin/env python3
"""Skill operation: list_invoices

Lists invoices for the authenticated FreshBooks account. Runs through Tabby's
POST /execute/fetch, i.e. fetch() inside the authenticated FreshBooks browser
session, so the session's own auth is applied by the browser and no token is
sniffed or passed from Python. See noui_runtime/freshbooks_api.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

# Make noui_runtime importable when this file is run as a standalone script
_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


async def _fetch(account_id: str, page: int, per_page: int) -> dict:
    query = urllib.parse.urlencode({"page": page, "per_page": per_page})
    path = f"/accounting/account/{account_id}/invoices/invoices?{query}"
    return await fb_request(path, account_id=account_id)


async def execute(status: str = "", page: int = 1, per_page: int = 15) -> dict:
    """List invoices for the authenticated FreshBooks account."""
    account_id = await get_account_id()
    data = await _fetch(account_id, page, per_page)
    result = ((data or {}).get("response") or {}).get("result") or {}
    raw = result.get("invoices", [])

    invoices = []
    for inv in raw:
        display_status = inv.get("display_status") or inv.get("v3_status") or ""
        if status and display_status.lower() != status.lower():
            continue
        amount = inv.get("amount") or {}
        client = (
            inv.get("current_organization")
            or inv.get("organization")
            or f"{inv.get('fname', '')} {inv.get('lname', '')}".strip()
        )
        invoices.append(
            {
                "id": inv.get("id"),
                "invoice_number": inv.get("invoice_number"),
                "client": client,
                "amount": amount.get("amount"),
                "currency": amount.get("code"),
                "status": display_status,
                "create_date": inv.get("create_date"),
                "due_date": inv.get("due_date"),
            }
        )

    return {
        "count": len(invoices),
        "page": result.get("page", page),
        "per_page": result.get("per_page", per_page),
        "total": result.get("total"),
        "invoices": invoices,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_invoices",
        description="List invoices for the authenticated FreshBooks account.",
    )
    parser.add_argument(
        "--status",
        dest="status",
        default="",
        help="Optional display-status filter: draft, sent, paid, viewed, overdue, partial. Empty = all.",
    )
    parser.add_argument("--page", dest="page", type=int, default=1, help="1-based page number.")
    parser.add_argument(
        "--per-page", dest="per_page", type=int, default=15, help="Invoices per page."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(status=args.status, page=args.page, per_page=args.per_page))
    except Exception as exc:
        print(f"list_invoices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and "error" in result:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

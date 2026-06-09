#!/usr/bin/env python3
"""Skill operation: list_bank_accounts

List bank/cash accounts (used as deposit / paid-through accounts for payments
and expenses) for the authenticated Zoho Books org. Read-only. Prints JSON.
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


async def execute() -> dict:
    """List bank/cash accounts (id, name, type, currency, balance)."""
    res = await books_request("bankaccounts")
    if res["status"] != 200:
        raise RuntimeError(f"bankaccounts API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("bankaccounts") or []
    accounts = [
        {
            "id": a.get("account_id"),
            "name": a.get("account_name"),
            "type": a.get("account_type"),
            "currency": a.get("currency_code"),
            "balance": a.get("balance"),
            "is_active": a.get("is_active"),
        }
        for a in raw
    ]
    return {"count": len(accounts), "accounts": accounts}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="list_bank_accounts").parse_args(argv)
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_bank_accounts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

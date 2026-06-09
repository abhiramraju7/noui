#!/usr/bin/env python3
"""Skill operation: list_accounts

Lists the chart of accounts from the Xero accounting API
(``GET api.xro/2.0/Accounts``): code, name, type, class, and tax type.

Prints JSON on stdout.
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

from noui_runtime.xero_api import xro_get  # noqa: E402


async def execute(account_type: str = "") -> dict:
    """List chart-of-accounts entries.

    Args:
        account_type: Optional filter on account Type (e.g. REVENUE, EXPENSE, BANK).

    Returns:
        {count, accounts: [{id, code, name, type, class, tax_type, status, description}]}
    """
    data = await xro_get("Accounts")
    raw = data.get("Accounts") or []
    needle = account_type.strip().upper()
    accounts = []
    for a in raw:
        if needle and (a.get("Type") or "").upper() != needle:
            continue
        accounts.append(
            {
                "id": a.get("AccountID"),
                "code": a.get("Code"),
                "name": a.get("Name"),
                "type": a.get("Type"),
                "class": a.get("Class"),
                "tax_type": a.get("TaxType"),
                "status": a.get("Status"),
                "description": a.get("Description"),
            }
        )
    return {"count": len(accounts), "accounts": accounts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_accounts",
        description="List the Xero chart of accounts.",
    )
    parser.add_argument(
        "--type",
        dest="account_type",
        default="",
        help="Filter by account Type (REVENUE, EXPENSE, BANK, etc.).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(account_type=args.account_type))
    except Exception as exc:
        print(f"list_accounts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

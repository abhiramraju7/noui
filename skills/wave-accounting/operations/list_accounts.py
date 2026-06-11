#!/usr/bin/env python3
"""Skill operation: list_accounts — list chart of accounts for the open business.

Runs through Tabby's POST /execute/fetch, i.e. fetch() inside the authenticated Wave browser session via GraphQL. See noui_runtime/wave_gql.py.
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

from noui_runtime.wave_gql import get_business_id, gql_request  # noqa: E402

_QUERY = """
query ($businessId: ID!, $page: Int!, $pageSize: Int!) {
  business(id: $businessId) {
    accounts(page: $page, pageSize: $pageSize) {
      edges {
        node {
          id
          name
          displayId
          balance
          type { value name }
          subtype { value name }
          isArchived
        }
      }
    }
  }
}
"""


async def execute(account_type: str = "", page: int = 1, page_size: int = 100) -> dict:
    business_id = await get_business_id()
    body = await gql_request(
        _QUERY, {"businessId": business_id, "page": page, "pageSize": page_size}
    )
    edges = (
        (((body.get("data") or {}).get("business") or {}).get("accounts") or {}).get("edges")
    ) or []
    needle = account_type.strip().upper()
    accounts = []
    for e in edges:
        a = e.get("node") or {}
        atype = ((a.get("type") or {}).get("value") or "").upper()
        if needle and needle != atype:
            continue
        accounts.append(
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "display_id": a.get("displayId"),
                "type": atype,
                "subtype": (a.get("subtype") or {}).get("value"),
                "balance": a.get("balance"),
                "is_archived": a.get("isArchived"),
            }
        )
    return {"count": len(accounts), "page": page, "accounts": accounts}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="list_accounts")
    p.add_argument("--type", dest="account_type", default="", help="INCOME/EXPENSE/ASSET/...")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=100)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(account_type=args.account_type, page=args.page, page_size=args.page_size)
        )
    except Exception as exc:
        print(f"list_accounts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

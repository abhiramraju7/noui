#!/usr/bin/env python3
"""Skill operation: list_customers — list Wave customers for the open business."""

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
    customers(page: $page, pageSize: $pageSize) {
      edges {
        node {
          id
          name
          email
          phone
          outstandingAmount { value }
        }
      }
    }
  }
}
"""


async def execute(query: str = "", page: int = 1, page_size: int = 50) -> dict:
    business_id = await get_business_id()
    body = await gql_request(
        _QUERY,
        {"businessId": business_id, "page": page, "pageSize": page_size},
    )
    edges = (
        (((body.get("data") or {}).get("business") or {}).get("customers") or {}).get("edges")
    ) or []
    needle = query.strip().lower()
    customers = []
    for e in edges:
        c = e.get("node") or {}
        name = c.get("name") or ""
        email = c.get("email") or ""
        if needle and needle not in f"{name} {email}".lower():
            continue
        customers.append(
            {
                "id": c.get("id"),
                "name": name,
                "email": email,
                "phone": c.get("phone"),
                "outstanding": (c.get("outstandingAmount") or {}).get("value"),
            }
        )
    return {"count": len(customers), "page": page, "customers": customers}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="list_customers")
    p.add_argument("--query", default="", help="Filter on name/email.")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(query=args.query, page=args.page, page_size=args.page_size))
    except Exception as exc:
        print(f"list_customers failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

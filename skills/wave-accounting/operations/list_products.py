#!/usr/bin/env python3
"""Skill operation: list_products — list products/services for the open business.

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
    products(page: $page, pageSize: $pageSize) {
      edges {
        node {
          id
          name
          description
          unitPrice
          isSold
          isBought
          isArchived
        }
      }
    }
  }
}
"""


async def execute(page: int = 1, page_size: int = 50) -> dict:
    business_id = await get_business_id()
    body = await gql_request(
        _QUERY, {"businessId": business_id, "page": page, "pageSize": page_size}
    )
    edges = (
        (((body.get("data") or {}).get("business") or {}).get("products") or {}).get("edges")
    ) or []
    products = [
        {
            "id": (e.get("node") or {}).get("id"),
            "name": (e.get("node") or {}).get("name"),
            "description": (e.get("node") or {}).get("description"),
            "unit_price": (e.get("node") or {}).get("unitPrice"),
            "is_sold": (e.get("node") or {}).get("isSold"),
            "is_bought": (e.get("node") or {}).get("isBought"),
            "is_archived": (e.get("node") or {}).get("isArchived"),
        }
        for e in edges
    ]
    return {"count": len(products), "page": page, "products": products}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="list_products")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(page=args.page, page_size=args.page_size))
    except Exception as exc:
        print(f"list_products failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

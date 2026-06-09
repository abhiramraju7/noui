#!/usr/bin/env python3
"""Skill operation: list_items

List items (products/services) for the authenticated Zoho Books org. Read-only.
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

from noui_runtime.zoho_books import books_request  # noqa: E402


async def execute(page: int = 1) -> dict:
    """List items (id, name, rate, description, tax)."""
    res = await books_request("items", params={"page": page, "per_page": 200})
    if res["status"] != 200:
        raise RuntimeError(f"items API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("items") or []
    items = [
        {
            "id": i.get("item_id"),
            "name": i.get("name"),
            "rate": i.get("rate"),
            "description": i.get("description"),
            "tax_id": i.get("tax_id"),
            "status": i.get("status"),
        }
        for i in raw
    ]
    return {"count": len(items), "page": page, "items": items}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="list_items", description="List Zoho Books items.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(page=args.page))
    except Exception as exc:
        print(f"list_items failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

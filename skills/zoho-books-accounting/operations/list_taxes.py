#!/usr/bin/env python3
"""Skill operation: list_taxes

List tax rates configured for the authenticated Zoho Books org. Read-only.
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


async def execute() -> dict:
    """List tax rates (id, name, percentage, type)."""
    res = await books_request("settings/taxes")
    if res["status"] != 200:
        raise RuntimeError(f"settings/taxes API returned {res['status']}: {str(res['body'])[:300]}")
    raw = (res["body"] or {}).get("taxes") or []
    taxes = [
        {
            "id": t.get("tax_id"),
            "name": t.get("tax_name"),
            "percentage": t.get("tax_percentage"),
            "type": t.get("tax_type"),
        }
        for t in raw
    ]
    return {"count": len(taxes), "taxes": taxes}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="list_taxes").parse_args(argv)
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_taxes failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

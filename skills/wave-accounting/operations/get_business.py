#!/usr/bin/env python3
"""Skill operation: get_business — fetch the open Wave business profile."""

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
query ($businessId: ID!) {
  business(id: $businessId) {
    id
    name
    currency { code name symbol }
    address { city country { name code } }
    isClassicAccounting
    isPersonal
  }
}
"""


async def execute() -> dict:
    business_id = await get_business_id()
    body = await gql_request(_QUERY, {"businessId": business_id})
    b = (body.get("data") or {}).get("business") or {}
    return {
        "id": b.get("id"),
        "name": b.get("name"),
        "currency": (b.get("currency") or {}).get("code"),
        "city": (b.get("address") or {}).get("city"),
        "country": ((b.get("address") or {}).get("country") or {}).get("code"),
        "is_classic_accounting": b.get("isClassicAccounting"),
        "is_personal": b.get("isPersonal"),
    }


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="get_business").parse_args(argv)
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"get_business failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

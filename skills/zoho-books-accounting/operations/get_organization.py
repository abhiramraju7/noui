#!/usr/bin/env python3
"""Skill operation: get_organization

Fetch the authenticated Zoho Books organization profile (name, currency,
country, fiscal year, tax settings). Read-only. Prints JSON on stdout.
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

from noui_runtime.zoho_books import books_request, get_org_id  # noqa: E402


async def execute() -> dict:
    """Return the profile of the currently-open Zoho Books organization."""
    org_id = await get_org_id()
    res = await books_request(f"organizations/{org_id}")
    if res["status"] != 200:
        raise RuntimeError(f"organizations API returned {res['status']}: {str(res['body'])[:300]}")
    o = (res["body"] or {}).get("organization") or {}
    return {
        "id": o.get("organization_id"),
        "name": o.get("name"),
        "currency": o.get("currency_code"),
        "country": o.get("country"),
        "time_zone": o.get("time_zone"),
        "fiscal_year_start_month": o.get("fiscal_year_start_month"),
        "is_gst_registered": o.get("is_gst_registered"),
        "tax_basis": o.get("tax_basis"),
        "plan": o.get("plan_type") if o.get("plan_type") is not None else o.get("plan_name"),
    }


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="get_organization").parse_args(argv)
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"get_organization failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

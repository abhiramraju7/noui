#!/usr/bin/env python3
"""List Vrbo stays meeting a minimum advertised discount through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.vrbo import get_stay_rates, search_stays


async def execute(
    destination: str,
    check_in: str,
    check_out: str,
    minimum_discount: float = 20,
    profile_slug: str | None = None,
) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "vrbo"
    result = await search_stays(destination, check_in, check_out, profile_slug=profile)
    stays = []
    for stay in result["stays"]:
        rate = await get_stay_rates(stay, profile_slug=profile)
        amounts = [item["amount"] for item in rate["rates"]]
        if len(amounts) < 2 or max(amounts) <= 0:
            continue
        discount = round((max(amounts) - min(amounts)) / max(amounts) * 100, 2)
        if discount >= minimum_discount:
            stays.append({**rate, "discount_percentage": discount})
    stays.sort(key=lambda item: item["discount_percentage"], reverse=True)
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "minimum_discount": minimum_discount,
        "results_count": len(stays),
        "stays": stays,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List discounted Vrbo stays.")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--check-in", required=True)
    parser.add_argument("--check-out", required=True)
    parser.add_argument("--minimum-discount", type=float, default=20)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            execute(
                args.destination,
                args.check_in,
                args.check_out,
                args.minimum_discount,
                args.profile_slug,
            )
        )
    except Exception as exc:
        print(f"list_discounted_stays failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

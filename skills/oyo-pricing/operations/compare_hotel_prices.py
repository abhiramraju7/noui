#!/usr/bin/env python3
"""Compare available OYO hotels by final public price through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.oyo import search_hotels


async def execute(
    destination: str,
    check_in: str,
    check_out: str,
    limit: int = 10,
    profile_slug: str | None = None,
) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "oyo"
    result = await search_hotels(destination, check_in, check_out, profile_slug=profile)
    hotels = [
        item
        for item in result["hotels"]
        if item["available"] and item["total_with_tax"] is not None
    ]
    hotels.sort(key=lambda item: item["total_with_tax"])
    selected = hotels[: max(1, limit)]
    return {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
        "results_count": len(selected),
        "hotels": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare OYO hotels by final public price.")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--check-in", required=True)
    parser.add_argument("--check-out", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            execute(args.destination, args.check_in, args.check_out, args.limit, args.profile_slug)
        )
    except Exception as exc:
        print(f"compare_hotel_prices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

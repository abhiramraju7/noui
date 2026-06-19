#!/usr/bin/env python3
"""Get Jumeirah's public base price, discount, tax, and final price through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.jumeirah import find_hotel, get_hotel_rates, search_hotels


async def execute(
    destination: str, hotel_id: str, check_in: str, check_out: str, profile_slug: str | None = None
) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "jumeirah-hotels"
    hotel = find_hotel(
        await search_hotels(destination, check_in, check_out, profile_slug=profile), hotel_id
    )
    result = await get_hotel_rates(hotel, profile_slug=profile)
    return {"check_in": check_in, "check_out": check_out, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Get a Jumeirah hotel's public price breakdown.")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--hotel-id", required=True)
    parser.add_argument("--check-in", required=True)
    parser.add_argument("--check-out", required=True)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            execute(
                args.destination, args.hotel_id, args.check_in, args.check_out, args.profile_slug
            )
        )
    except Exception as exc:
        print(f"get_price_breakdown failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

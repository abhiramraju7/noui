#!/usr/bin/env python3
"""Search Selina stays and return normalized public prices through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.selina import search_stays


async def execute(
    destination: str,
    check_in: str,
    check_out: str,
    rooms: int = 1,
    adults: int = 2,
    children: int = 0,
    profile_slug: str | None = None,
) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "selina"
    return await search_stays(
        destination,
        check_in,
        check_out,
        rooms=rooms,
        adults=adults,
        children=children,
        profile_slug=profile,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Selina stays by destination and dates.")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--check-in", required=True)
    parser.add_argument("--check-out", required=True)
    parser.add_argument("--rooms", type=int, default=1)
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            execute(
                args.destination,
                args.check_in,
                args.check_out,
                args.rooms,
                args.adults,
                args.children,
                args.profile_slug,
            )
        )
    except Exception as exc:
        print(f"search_stays failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

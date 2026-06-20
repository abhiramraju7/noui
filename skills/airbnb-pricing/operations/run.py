#!/usr/bin/env python3
"""Search the public travel product through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.meta import run_public_search


async def execute(**kwargs: object) -> dict:
    profile = str(kwargs.pop("profile_slug", "") or os.environ.get("PROFILE_SLUG") or "airbnb")
    return await run_public_search(profile_slug=profile, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="")
    parser.add_argument("--origin", default="")
    parser.add_argument("--destination", default="")
    parser.add_argument("--departure", default="")
    parser.add_argument("--return-date", default="")
    parser.add_argument("--check-in", default="")
    parser.add_argument("--check-out", default="")
    parser.add_argument("--pickup", default="")
    parser.add_argument("--dropoff", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--transport",
        choices=("auto", "fetch", "browser", "http"),
        default="auto",
        help="Execution strategy. auto tries fetch, browser+HAR, then guarded HTTP.",
    )
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            execute(
                query=args.query,
                origin=args.origin,
                destination=args.destination,
                departure=args.departure,
                return_date=args.return_date,
                check_in=args.check_in,
                check_out=args.check_out,
                pickup=args.pickup,
                dropoff=args.dropoff,
                url=args.url,
                adults=args.adults,
                limit=args.limit,
                transport=args.transport,
                profile_slug=args.profile_slug,
            )
        )
    except Exception as exc:
        print(f"compare_home_prices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

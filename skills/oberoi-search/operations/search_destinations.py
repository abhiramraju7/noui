#!/usr/bin/env python3
"""Search Oberoi destinations through Tabby-routed execute/fetch."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.oberoi import search_destinations


async def execute(query: str, limit: int = 10, profile_slug: str | None = None) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "oberoi-hotels"
    suggestions = await search_destinations(query, profile_slug=profile, limit=limit)
    return {"query": query, "results_count": len(suggestions), "destinations": suggestions}


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Oberoi cities and neighbourhoods.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args.query, args.limit, args.profile_slug))
    except Exception as exc:
        print(f"search_destinations failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""List public Couchsurfing community/place links through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.couchsurfing import list_community_links


async def execute(query: str = "", limit: int = 20, profile_slug: str | None = None) -> list[dict]:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "couchsurfing"
    return await list_community_links(query, limit=limit, profile_slug=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args.query, args.limit, args.profile_slug))
    except Exception as exc:
        print(f"list_community_links failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

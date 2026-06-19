#!/usr/bin/env python3
"""Get one public Couchsurfing event page through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.couchsurfing import get_public_page


async def execute(url: str, profile_slug: str | None = None) -> dict:
    profile = profile_slug or os.environ.get("PROFILE_SLUG") or "couchsurfing"
    return await get_public_page(url, profile_slug=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args.url, args.profile_slug))
    except Exception as exc:
        print(f"get_event_details failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

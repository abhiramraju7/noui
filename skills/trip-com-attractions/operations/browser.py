#!/usr/bin/env python3
"""Inspect or automate a bounded browser workflow through Tabby."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.browser_tools import run_browser_tools
from noui_runtime.meta import PROFILE


async def execute(**kwargs: object) -> dict:
    raw_actions = kwargs.pop("actions_json", "[]")
    actions = json.loads(str(raw_actions or "[]"))
    if not isinstance(actions, list) or not all(isinstance(item, dict) for item in actions):
        raise ValueError("actions_json must be a JSON array of objects")
    profile = str(kwargs.pop("profile_slug", "") or os.environ.get("PROFILE_SLUG") or PROFILE)
    return await run_browser_tools(profile_slug=profile, actions=actions, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--mode", choices=("inspect", "workflow", "discover"), default="inspect")
    parser.add_argument("--actions-json", default="[]")
    parser.add_argument("--screenshot", action="store_true")
    parser.add_argument("--allow-transactional", action="store_true")
    parser.add_argument("--profile-slug")
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(**vars(args)))
    except Exception as exc:
        print(f"browser_tools failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

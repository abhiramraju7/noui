#!/usr/bin/env python3
"""Capture and compare a normalized travel-price snapshot."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noui_runtime.meta import PROFILE, run_public_search


def _load_json(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    raw = value
    if not value.lstrip().startswith("{"):
        path = Path(value).expanduser()
        if path.is_file():
            raw = path.read_text()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("snapshot JSON must be an object")
    return parsed


def _fingerprint(payload: dict[str, Any]) -> str:
    normalized = {
        "source_url": payload.get("source_url"),
        "results": payload.get("results", []),
        "prices": payload.get("prices", []),
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _compare(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {"changed": None, "added_prices": [], "removed_prices": []}
    old_prices = {json.dumps(item, sort_keys=True) for item in previous.get("prices", [])}
    new_prices = {json.dumps(item, sort_keys=True) for item in current.get("prices", [])}
    return {
        "changed": _fingerprint(previous) != _fingerprint(current),
        "added_prices": [json.loads(item) for item in sorted(new_prices - old_prices)],
        "removed_prices": [json.loads(item) for item in sorted(old_prices - new_prices)],
        "previous_results_count": previous.get("results_count"),
        "current_results_count": current.get("results_count"),
    }


async def execute(
    *,
    search_json: str,
    previous: str = "",
    output: str = "",
    profile_slug: str = PROFILE,
) -> dict[str, Any]:
    search = json.loads(search_json or "{}")
    if not isinstance(search, dict):
        raise ValueError("search_json must be a JSON object")
    search.pop("profile_slug", None)
    current = await run_public_search(profile_slug=profile_slug, **search)
    prior = _load_json(previous)
    result = {
        "snapshot_id": _fingerprint(current),
        "comparison": _compare(prior, current),
        "snapshot": current,
    }
    if output:
        path = Path(output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2) + "\n")
        result["saved_to"] = str(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-json", required=True)
    parser.add_argument("--previous", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--profile-slug", default=os.environ.get("PROFILE_SLUG") or PROFILE)
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(**vars(args)))
    except Exception as exc:
        print(f"price_snapshot failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

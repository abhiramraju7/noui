#!/usr/bin/env python3
"""Skill operation: list_branding_themes

Lists invoice branding themes from the Xero accounting API
(``GET api.xro/2.0/BrandingThemes``). The branding theme id is required when
creating invoices.

Prints JSON on stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.xero_api import xro_get  # noqa: E402


async def execute() -> dict:
    """List invoice branding themes for the authenticated Xero org."""
    data = await xro_get("BrandingThemes")
    raw = data.get("BrandingThemes") or []
    themes = [
        {
            "id": t.get("BrandingThemeID"),
            "name": t.get("Name"),
            "sort_order": t.get("SortOrder"),
            "logo_url": t.get("LogoUrl"),
        }
        for t in raw
    ]
    return {"count": len(themes), "branding_themes": themes}


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_branding_themes failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

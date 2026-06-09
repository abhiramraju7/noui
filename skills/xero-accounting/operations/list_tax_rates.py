#!/usr/bin/env python3
"""Skill operation: list_tax_rates

Lists tax rates from the Xero accounting API (``GET api.xro/2.0/TaxRates``):
name, tax type, effective rate, what the rate can apply to, and components.

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
    """List tax rates for the authenticated Xero org."""
    data = await xro_get("TaxRates")
    raw = data.get("TaxRates") or []
    rates = []
    for r in raw:
        rates.append(
            {
                "name": r.get("Name"),
                "tax_type": r.get("TaxType"),
                "display_rate": r.get("DisplayTaxRate"),
                "effective_rate": r.get("EffectiveRate"),
                "status": r.get("Status"),
                "can_apply_to_revenue": r.get("CanApplyToRevenue"),
                "can_apply_to_expenses": r.get("CanApplyToExpenses"),
                "components": [
                    {"name": c.get("Name"), "rate": c.get("Rate")}
                    for c in (r.get("TaxComponents") or [])
                ],
            }
        )
    return {"count": len(rates), "tax_rates": rates}


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"list_tax_rates failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

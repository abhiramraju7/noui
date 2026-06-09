#!/usr/bin/env python3
"""Skill operation: get_organisation

Fetches organisation details from the Xero accounting API
(``GET api.xro/2.0/Organisation``): name, currency, tax settings, edition,
financial year end, and next document numbers.

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
    """Return organisation profile for the authenticated Xero org."""
    data = await xro_get("Organisation")
    orgs = data.get("Organisations") or []
    if not orgs:
        return {}
    o = orgs[0]
    return {
        "name": o.get("Name"),
        "legal_name": o.get("LegalName"),
        "organisation_id": o.get("OrganisationID"),
        "short_code": o.get("ShortCode"),
        "base_currency": o.get("BaseCurrency"),
        "country_code": o.get("CountryCode"),
        "edition": o.get("Edition"),
        "class": o.get("Class"),
        "pays_tax": o.get("PaysTax"),
        "default_sales_tax": o.get("DefaultSalesTax"),
        "default_purchases_tax": o.get("DefaultPurchasesTax"),
        "financial_year_end_day": o.get("FinancialYearEndDay"),
        "financial_year_end_month": o.get("FinancialYearEndMonth"),
        "timezone": o.get("Timezone"),
        "next_invoice_number": o.get("NextInvoiceNumber"),
        "next_credit_note_number": o.get("NextCreditNoteNumber"),
        "next_purchase_order_number": o.get("NextPurchaseOrderNumber"),
        "is_demo_company": o.get("IsDemoCompany"),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        result = asyncio.run(execute())
    except Exception as exc:
        print(f"get_organisation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

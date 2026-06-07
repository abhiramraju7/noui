#!/usr/bin/env python3
"""Skill operation: get_sales_tax_summary

Fetches the FreshBooks Sales Tax Summary report for the authenticated business.
Runs inside Tabby's authenticated browser via CDP. The FreshBooks accounting API
authenticates with a short-lived in-memory bearer token (not cookies) and serves
wildcard CORS, so the request uses credentials:'omit' plus a sniffed Authorization
header. See noui_runtime/freshbooks_auth.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.cdp import cdp_eval, find_page  # noqa: E402
from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_auth import get_bearer  # noqa: E402

API_BASE = "https://api.freshbooks.com"
PAGE_MATCH = "my.freshbooks.com"
API_VERSION = "2023-02-20"


def _money(node: dict | None) -> dict:
    """Flatten a FreshBooks money node to {amount, currency}."""
    node = node or {}
    return {"amount": node.get("amount"), "currency": node.get("code")}


def _tax_line(row: dict) -> dict:
    """Flatten a single tax row into a readable summary."""
    return {
        "tax_name": row.get("tax_name"),
        "tax_collected": _money(row.get("tax_collected")),
        "tax_paid": _money(row.get("tax_paid")),
        "net_tax": _money(row.get("net_tax")),
        "taxable_amount_collected": _money(row.get("taxable_amount_collected")),
        "net_taxable_amount": _money(row.get("net_taxable_amount")),
    }


async def _fetch(
    ws_url: str,
    bearer: str,
    account_id: str,
    start_date: str,
    end_date: str,
    currency_code: str,
    cash_based: bool,
) -> dict:
    query = urllib.parse.urlencode(
        {
            "start_date": start_date,
            "end_date": end_date,
            "currency_code": currency_code,
            "locale": "en",
            "cash_based": "true" if cash_based else "false",
        }
    )
    url = f"{API_BASE}/accounting/account/{account_id}/reports/accounting/taxsummary?{query}"
    init = {
        "method": "GET",
        "credentials": "omit",
        "headers": {
            "Authorization": bearer,
            "X-API-VERSION": API_VERSION,
            "X-Account-ID": account_id,
            "Accept": "application/json",
        },
    }
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)


async def execute(
    start_date: str,
    end_date: str,
    currency_code: str = "USD",
    cash_based: bool = False,
) -> dict:
    """Fetch the Sales Tax Summary report for a date range.

    Args:
        start_date: Period start, YYYY-MM-DD.
        end_date: Period end, YYYY-MM-DD.
        currency_code: ISO currency code (default USD).
        cash_based: Cash-basis (True) vs accrual (False, default) accounting.

    Returns:
        {start_date, end_date, currency_code, cash_based, total_invoiced,
         total_tax_collected, taxes: [{tax_name, tax_collected, tax_paid,
         net_tax, taxable_amount_collected, net_taxable_amount}, ...]}
    """
    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required (YYYY-MM-DD).")

    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            "`tabby session ensure --profile freshbooks` and open my.freshbooks.com."
        )

    bearer = await get_bearer()
    account_id = await get_account_id(ws_url, bearer)
    res = await _fetch(ws_url, bearer, account_id, start_date, end_date, currency_code, cash_based)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        res = await _fetch(
            ws_url, bearer, account_id, start_date, end_date, currency_code, cash_based
        )

    if res.get("status") != 200:
        raise RuntimeError(
            f"FreshBooks Sales Tax Summary returned {res.get('status')}: "
            f"{str(res.get('body'))[:300]}"
        )

    ts = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "taxsummary", {}
    )

    taxes = [_tax_line(r) for r in (ts.get("taxes") or [])]
    total_collected = sum(
        float(((r.get("tax_collected") or {}).get("amount")) or 0) for r in (ts.get("taxes") or [])
    )

    return {
        "start_date": ts.get("start_date"),
        "end_date": ts.get("end_date"),
        "currency_code": ts.get("currency_code"),
        "cash_based": ts.get("cash_based"),
        "total_invoiced": _money(ts.get("total_invoiced")),
        "total_tax_collected": {
            "amount": f"{total_collected:.2f}",
            "currency": ts.get("currency_code"),
        },
        "taxes": taxes,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="get_sales_tax_summary",
        description="Fetch the FreshBooks Sales Tax Summary report for a date range.",
    )
    parser.add_argument(
        "--start-date", dest="start_date", required=True, help="Period start, YYYY-MM-DD."
    )
    parser.add_argument(
        "--end-date", dest="end_date", required=True, help="Period end, YYYY-MM-DD."
    )
    parser.add_argument(
        "--currency-code", dest="currency_code", default="USD", help="ISO currency code."
    )
    parser.add_argument(
        "--cash-based", dest="cash_based", action="store_true", help="Use cash-basis accounting."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                start_date=args.start_date,
                end_date=args.end_date,
                currency_code=args.currency_code,
                cash_based=args.cash_based,
            )
        )
    except Exception as exc:
        print(f"get_sales_tax_summary failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and "error" in result:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Skill operation: get_profit_and_loss

Fetches the FreshBooks Profit & Loss report for the authenticated business.
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
from noui_runtime.freshbooks_account import get_business_uuid  # noqa: E402
from noui_runtime.freshbooks_auth import get_bearer  # noqa: E402

API_BASE = "https://api.freshbooks.com"
PAGE_MATCH = "my.freshbooks.com"
API_VERSION = "2023-02-20"


def _line(node: dict | None) -> dict:
    """Flatten a P&L summary node to {description, amount, currency}."""
    node = node or {}
    total = node.get("total") or {}
    return {
        "description": node.get("description"),
        "amount": total.get("amount"),
        "currency": total.get("code"),
    }


async def _fetch(
    ws_url: str,
    bearer: str,
    business_uuid: str,
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
            "sort_by": "name",
        }
    )
    url = f"{API_BASE}/accounting/businesses/{business_uuid}/reports/profit_and_loss?{query}"
    init = {
        "method": "GET",
        "credentials": "omit",
        "headers": {
            "Authorization": bearer,
            "X-API-VERSION": API_VERSION,
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
    """Fetch the Profit & Loss report for a date range.

    Args:
        start_date: Period start, YYYY-MM-DD.
        end_date: Period end, YYYY-MM-DD.
        currency_code: ISO currency code (default USD).
        cash_based: Cash-basis (True) vs accrual (False, default) accounting.

    Returns:
        {company_name, start_date, end_date, currency_code, cash_based,
         total_income, total_expenses, net_profit, gross_margin,
         income: [...], expenses: [...]}
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
    business_uuid = await get_business_uuid(ws_url, bearer)
    res = await _fetch(
        ws_url, bearer, business_uuid, start_date, end_date, currency_code, cash_based
    )
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        res = await _fetch(
            ws_url, bearer, business_uuid, start_date, end_date, currency_code, cash_based
        )

    if res.get("status") != 200:
        raise RuntimeError(
            f"FreshBooks P&L report returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    pl = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "profit_and_loss", {}
    )

    return {
        "company_name": pl.get("company_name"),
        "start_date": pl.get("start_date"),
        "end_date": pl.get("end_date"),
        "currency_code": pl.get("currency_code"),
        "cash_based": pl.get("cash_based"),
        "total_income": _line(pl.get("total_income")),
        "total_expenses": _line(pl.get("total_expenses")),
        "net_profit": _line(pl.get("net_profit")),
        "gross_margin": _line(pl.get("gross_margin")),
        "income": [_line(n) for n in (pl.get("income") or [])],
        "expenses": [_line(n) for n in (pl.get("expenses") or [])],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="get_profit_and_loss",
        description="Fetch the FreshBooks Profit & Loss report for a date range.",
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
        print(f"get_profit_and_loss failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and "error" in result:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

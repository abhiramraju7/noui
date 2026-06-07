#!/usr/bin/env python3
"""Skill operation: get_accounts_receivable_aging

Fetches the FreshBooks Accounts Receivable (A/R) aging report: per-client
outstanding balances bucketed by age (0-30, 31-60, 61-90, 91+ days). Runs inside
Tabby's authenticated browser via CDP using a sniffed in-memory bearer token.
See noui_runtime/freshbooks_auth.py.

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

BUCKETS = ["0-30", "31-60", "61-90", "91+"]


def _amt(node: dict | None) -> float:
    try:
        return float(((node or {}).get("amount")) or 0)
    except (TypeError, ValueError):
        return 0.0


async def _fetch(
    ws_url: str, bearer: str, account_id: str, start_date: str, end_date: str, currency_code: str
) -> dict:
    query = urllib.parse.urlencode(
        {
            "start_date": start_date,
            "end_date": end_date,
            "currency_code": currency_code,
            "locale": "en",
        }
    )
    url = f"{API_BASE}/accounting/account/{account_id}/reports/accounting/accounts_aging?{query}"
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
) -> dict:
    """Fetch the Accounts Receivable aging report for a date range.

    Args:
        start_date: Period start, YYYY-MM-DD.
        end_date: Period end, YYYY-MM-DD.
        currency_code: ISO currency code (default USD).

    Returns:
        {start_date, end_date, currency_code, total_outstanding,
         buckets: {"0-30": .., "31-60": .., "61-90": .., "91+": ..},
         clients: [{client, email, "0-30", "31-60", "61-90", "91+", total}]}
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
    res = await _fetch(ws_url, bearer, account_id, start_date, end_date, currency_code)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        res = await _fetch(ws_url, bearer, account_id, start_date, end_date, currency_code)

    if res.get("status") != 200:
        raise RuntimeError(
            f"FreshBooks A/R aging report returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    aging = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "accounts_aging", {}
    )
    rows = aging.get("accounts") or []

    bucket_totals = dict.fromkeys(BUCKETS, 0.0)
    clients = []
    for r in rows:
        client = (
            r.get("organization") or ""
        ).strip() or f"{r.get('fname', '')} {r.get('lname', '')}".strip()
        entry = {"client": client, "email": r.get("email")}
        for b in BUCKETS:
            val = _amt(r.get(b))
            bucket_totals[b] += val
            entry[b] = f"{val:.2f}"
        entry["total"] = f"{_amt(r.get('total')):.2f}"
        clients.append(entry)

    total_outstanding = sum(bucket_totals.values())
    return {
        "start_date": start_date,
        "end_date": end_date,
        "currency_code": currency_code,
        "total_outstanding": f"{total_outstanding:.2f}",
        "buckets": {b: f"{bucket_totals[b]:.2f}" for b in BUCKETS},
        "clients": clients,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="get_accounts_receivable_aging",
        description="Fetch the FreshBooks Accounts Receivable aging report for a date range.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                start_date=args.start_date,
                end_date=args.end_date,
                currency_code=args.currency_code,
            )
        )
    except Exception as exc:
        print(f"get_accounts_receivable_aging failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

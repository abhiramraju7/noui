#!/usr/bin/env python3
"""Skill operation: list_expenses

Lists expenses for the authenticated FreshBooks account. Runs inside Tabby's
authenticated browser via CDP using a sniffed in-memory bearer token.
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


async def _fetch_categories(ws_url: str, bearer: str, account_id: str) -> dict:
    url = f"{API_BASE}/accounting/account/{account_id}/expenses/categories?per_page=200"
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
    res = await cdp_eval(ws_url, js)
    if res.get("status") != 200:
        return {}
    cats = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "categories", []
    )
    return {c.get("categoryid"): c.get("category") for c in cats}


async def _fetch(ws_url: str, bearer: str, account_id: str, page: int, per_page: int) -> dict:
    query = urllib.parse.urlencode({"page": page, "per_page": per_page})
    url = f"{API_BASE}/accounting/account/{account_id}/expenses/expenses?{query}"
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


async def execute(page: int = 1, per_page: int = 50) -> dict:
    """List expenses for the authenticated FreshBooks account.

    Returns:
        {count, page, per_page, total, expenses: [{id, vendor, amount, currency,
         category, date, notes}]}
    """
    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            "`tabby session ensure --profile freshbooks` and open my.freshbooks.com."
        )

    bearer = await get_bearer()
    account_id = await get_account_id(ws_url, bearer)
    res = await _fetch(ws_url, bearer, account_id, page, per_page)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        res = await _fetch(ws_url, bearer, account_id, page, per_page)

    if res.get("status") != 200:
        raise RuntimeError(
            f"FreshBooks expenses API returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    result = ((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}
    raw = result.get("expenses", [])
    cat_names = await _fetch_categories(ws_url, bearer, account_id) if raw else {}

    expenses = []
    for e in raw:
        amount = e.get("amount") or {}
        expenses.append(
            {
                "id": e.get("id"),
                "vendor": e.get("vendor"),
                "amount": amount.get("amount"),
                "currency": amount.get("code"),
                "category": cat_names.get(e.get("categoryid")),
                "date": e.get("date"),
                "notes": e.get("notes"),
            }
        )

    return {
        "count": len(expenses),
        "page": result.get("page", page),
        "per_page": result.get("per_page", per_page),
        "total": result.get("total"),
        "expenses": expenses,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_expenses",
        description="List expenses for the authenticated FreshBooks account.",
    )
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    parser.add_argument(
        "--per-page", dest="per_page", type=int, default=50, help="Expenses per page."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(page=args.page, per_page=args.per_page))
    except Exception as exc:
        print(f"list_expenses failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

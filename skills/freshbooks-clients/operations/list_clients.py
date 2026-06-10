#!/usr/bin/env python3
"""Skill operation: list_clients

Lists clients for the authenticated FreshBooks account, with an optional
name/organization filter. Runs through Tabby's POST /execute/fetch, i.e. fetch()
inside the authenticated FreshBooks browser session. See noui_runtime/freshbooks_api.py.

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

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


def _label(c: dict) -> str:
    org = (c.get("organization") or "").strip()
    person = f"{c.get('fname', '')} {c.get('lname', '')}".strip()
    return org or person or f"client {c.get('id')}"


async def _fetch(account_id: str, page: int, per_page: int) -> dict:
    query = urllib.parse.urlencode({"page": page, "per_page": per_page})
    path = f"/accounting/account/{account_id}/users/clients?{query}"
    return await fb_request(path, account_id=account_id)


async def execute(query: str = "", page: int = 1, per_page: int = 50) -> dict:
    """List clients for the authenticated FreshBooks account.

    Args:
        query: Optional case-insensitive filter on name/organization/email.
        page: 1-based page number.
        per_page: Clients per page.

    Returns:
        {count, page, per_page, total, clients: [{id, organization, name, email,
         currency, country, city}]}
    """
    account_id = await get_account_id()
    data = await _fetch(account_id, page, per_page)
    result = ((data or {}).get("response") or {}).get("result") or {}
    raw = result.get("clients", [])

    needle = query.strip().lower()
    clients = []
    for c in raw:
        name = f"{c.get('fname', '')} {c.get('lname', '')}".strip()
        haystack = f"{c.get('organization', '')} {name} {c.get('email', '')}".lower()
        if needle and needle not in haystack:
            continue
        clients.append(
            {
                "id": c.get("id"),
                "organization": c.get("organization"),
                "name": name,
                "email": c.get("email"),
                "currency": c.get("currency_code"),
                "country": c.get("p_country"),
                "city": c.get("p_city"),
            }
        )

    return {
        "count": len(clients),
        "page": result.get("page", page),
        "per_page": result.get("per_page", per_page),
        "total": result.get("total"),
        "clients": clients,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_clients",
        description="List clients for the authenticated FreshBooks account.",
    )
    parser.add_argument("--query", default="", help="Filter on name/organization/email.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    parser.add_argument(
        "--per-page", dest="per_page", type=int, default=50, help="Clients per page."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(query=args.query, page=args.page, per_page=args.per_page))
    except Exception as exc:
        print(f"list_clients failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

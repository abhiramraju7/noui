#!/usr/bin/env python3
"""Skill operation: list_contacts

Lists contacts (customers/vendors) for the authenticated Zoho Books org, with an
optional name filter. Runs through Tabby's POST /execute/fetch. See noui_runtime/zoho_books.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.zoho_books import books_request  # noqa: E402


async def execute(query: str = "", contact_type: str = "", page: int = 1) -> dict:
    """List contacts for the authenticated Zoho Books organization.

    Args:
        query: Optional case-insensitive filter on contact/company name or email.
        contact_type: Optional filter: "customer" or "vendor".
        page: 1-based page number.

    Returns:
        {count, page, contacts: [{id, name, company, email, type, status, outstanding}]}
    """
    params: dict = {"page": page, "per_page": 200}
    if contact_type:
        params["contact_type"] = contact_type
    res = await books_request("contacts", params=params)
    if res["status"] != 200:
        raise RuntimeError(
            f"Zoho Books contacts API returned {res['status']}: {str(res['body'])[:300]}"
        )

    raw = (res["body"] or {}).get("contacts") or []
    needle = query.strip().lower()
    contacts = []
    for c in raw:
        name = c.get("contact_name") or ""
        company = c.get("company_name") or ""
        email = c.get("email") or ""
        if needle and needle not in f"{name} {company} {email}".lower():
            continue
        contacts.append(
            {
                "id": c.get("contact_id"),
                "name": name,
                "company": company,
                "email": email,
                "type": c.get("contact_type"),
                "status": c.get("status"),
                "outstanding": c.get("outstanding_receivable_amount"),
            }
        )
    return {"count": len(contacts), "page": page, "contacts": contacts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="list_contacts", description="List Zoho Books contacts.")
    parser.add_argument("--query", default="", help="Filter on name/company/email.")
    parser.add_argument(
        "--type",
        dest="contact_type",
        default="",
        choices=["", "customer", "vendor"],
        help="Filter by contact type.",
    )
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(query=args.query, contact_type=args.contact_type, page=args.page)
        )
    except Exception as exc:
        print(f"list_contacts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

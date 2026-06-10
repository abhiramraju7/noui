#!/usr/bin/env python3
"""Skill operation: list_contacts

Lists contacts for the authenticated Xero organisation, with an optional
name/email filter. Runs through Tabby's POST /execute/fetch inside the
authenticated Xero browser session. See noui_runtime/xero_api.py.

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

from noui_runtime.xero_api import xro_get  # noqa: E402


async def execute(query: str = "", page: int = 1) -> dict:
    """List contacts for the authenticated Xero organisation.

    Args:
        query: Optional case-insensitive filter on name/email.
        page: 1-based page number.

    Returns:
        {count, page, contacts: [{id, name, email, status, is_customer, is_supplier}]}
    """
    data = await xro_get(f"Contacts?page={page}")
    raw = data.get("Contacts") or []
    needle = query.strip().lower()
    contacts = []
    for c in raw:
        name = c.get("Name") or ""
        email = c.get("EmailAddress") or ""
        if needle and needle not in f"{name} {email}".lower():
            continue
        contacts.append(
            {
                "id": c.get("ContactID"),
                "name": name,
                "email": email,
                "status": c.get("ContactStatus"),
                "is_customer": c.get("IsCustomer"),
                "is_supplier": c.get("IsSupplier"),
            }
        )

    return {"count": len(contacts), "page": page, "contacts": contacts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_contacts",
        description="List contacts for the authenticated Xero organisation.",
    )
    parser.add_argument("--query", default="", help="Filter on name/email.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(query=args.query, page=args.page))
    except Exception as exc:
        print(f"list_contacts failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

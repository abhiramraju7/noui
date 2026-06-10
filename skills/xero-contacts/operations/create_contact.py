#!/usr/bin/env python3
"""Skill operation: create_contact

Creates a new contact in the authenticated Xero organisation. Runs through
Tabby's POST /execute/fetch inside the authenticated Xero browser session.
See noui_runtime/xero_api.py.

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

from noui_runtime.xero_api import xro_post  # noqa: E402


async def execute(
    name: str,
    email: str = "",
    is_customer: bool = True,
    is_supplier: bool = False,
) -> dict:
    """Create a contact in Xero.

    Args:
        name: Contact or company name (required).
        email: Contact email.
        is_customer: Mark as a customer (default True).
        is_supplier: Mark as a supplier.

    Returns:
        {id, name, email, status, is_customer, is_supplier}
    """
    if not name.strip():
        raise ValueError("--name is required.")

    payload: dict = {
        "Name": name.strip(),
        "IsCustomer": is_customer,
        "IsSupplier": is_supplier,
    }
    if email:
        payload["EmailAddress"] = email.strip()

    data = await xro_post("Contacts", {"Contacts": [payload]})
    c = (data.get("Contacts") or [{}])[0]
    return {
        "id": c.get("ContactID"),
        "name": c.get("Name"),
        "email": c.get("EmailAddress"),
        "status": c.get("ContactStatus"),
        "is_customer": c.get("IsCustomer"),
        "is_supplier": c.get("IsSupplier"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_contact",
        description="Create a contact in the authenticated Xero organisation.",
    )
    parser.add_argument("--name", required=True, help="Contact or company name.")
    parser.add_argument("--email", default="", help="Contact email.")
    parser.add_argument(
        "--customer",
        dest="is_customer",
        action="store_true",
        default=True,
        help="Mark as a customer (default).",
    )
    parser.add_argument(
        "--supplier", dest="is_supplier", action="store_true", help="Mark as a supplier."
    )
    parser.add_argument(
        "--no-customer", dest="is_customer", action="store_false", help="Do not mark as customer."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                name=args.name,
                email=args.email,
                is_customer=args.is_customer,
                is_supplier=args.is_supplier,
            )
        )
    except Exception as exc:
        print(f"create_contact failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

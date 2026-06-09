#!/usr/bin/env python3
"""Skill operation: create_contact

Creates a contact (customer or vendor) in the authenticated Zoho Books org.
Runs inside Tabby's authenticated browser via CDP (cookie auth + sniffed
X-ZCSRF-TOKEN). Writes data.

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


async def execute(
    name: str,
    email: str = "",
    company: str = "",
    contact_type: str = "customer",
    phone: str = "",
) -> dict:
    """Create a Zoho Books contact.

    Args:
        name: Contact display name (required).
        email: Primary contact email.
        company: Company name (defaults to ``name``).
        contact_type: "customer" or "vendor".
        phone: Optional phone number.

    Returns:
        {id, name, company, email, type, status}
    """
    payload: dict = {
        "contact_name": name,
        "company_name": company or name,
        "contact_type": contact_type,
    }
    contact_person: dict = {}
    if email:
        contact_person["email"] = email
    if phone:
        contact_person["phone"] = phone
    if contact_person:
        payload["contact_persons"] = [contact_person]

    res = await books_request("contacts", method="POST", body=payload)
    body = res["body"] or {}
    if res["status"] not in (200, 201) or body.get("code") not in (0, None):
        raise RuntimeError(f"create_contact failed ({res['status']}): {str(body)[:300]}")

    c = body.get("contact") or {}
    return {
        "id": c.get("contact_id"),
        "name": c.get("contact_name"),
        "company": c.get("company_name"),
        "email": (c.get("contact_persons") or [{}])[0].get("email") if c.get("contact_persons") else email,
        "type": c.get("contact_type"),
        "status": c.get("status"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="create_contact", description="Create a Zoho Books contact.")
    parser.add_argument("--name", required=True, help="Contact display name.")
    parser.add_argument("--email", default="", help="Primary contact email.")
    parser.add_argument("--company", default="", help="Company name (defaults to --name).")
    parser.add_argument(
        "--type", dest="contact_type", default="customer", choices=["customer", "vendor"],
        help="Contact type.",
    )
    parser.add_argument("--phone", default="", help="Phone number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                name=args.name, email=args.email, company=args.company,
                contact_type=args.contact_type, phone=args.phone,
            )
        )
    except Exception as exc:
        print(f"create_contact failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

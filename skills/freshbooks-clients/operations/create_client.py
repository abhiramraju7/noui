#!/usr/bin/env python3
"""Skill operation: create_client

Creates a new client (customer) in the authenticated FreshBooks account. Runs inside
Tabby's POST /execute/fetch, i.e. fetch() inside the authenticated FreshBooks
browser session. See noui_runtime/freshbooks_api.py.

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

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


async def _api(account_id: str, method: str, path: str, body: dict | None = None) -> dict:
    return await fb_request(
        f"/accounting/account/{account_id}/{path}",
        method=method,
        account_id=account_id,
        body=body,
    )


async def execute(
    organization: str = "",
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    currency_code: str = "USD",
    phone: str = "",
    city: str = "",
    country: str = "",
) -> dict:
    """Create a client in FreshBooks.

    Args:
        organization: Company/organization name.
        first_name: Contact first name.
        last_name: Contact last name.
        email: Contact email.
        currency_code: ISO currency code (default USD).
        phone: Contact phone.
        city: Billing city.
        country: Billing country.

    Returns:
        {id, organization, name, email, currency, country, city}
    """
    if not (organization or first_name or last_name):
        raise ValueError("Provide at least --organization or a --first-name/--last-name.")

    client_payload: dict = {"currency_code": currency_code}
    if organization:
        client_payload["organization"] = organization
    if first_name:
        client_payload["fname"] = first_name
    if last_name:
        client_payload["lname"] = last_name
    if email:
        client_payload["email"] = email
    if phone:
        client_payload["home_phone"] = phone
    if city:
        client_payload["p_city"] = city
    if country:
        client_payload["p_country"] = country

    account_id = await get_account_id()
    data = await _api(account_id, "POST", "users/clients", {"client": client_payload})
    c = (((data or {}).get("response") or {}).get("result") or {}).get("client", {})
    return {
        "id": c.get("id"),
        "organization": c.get("organization"),
        "name": f"{c.get('fname', '')} {c.get('lname', '')}".strip(),
        "email": c.get("email"),
        "currency": c.get("currency_code"),
        "country": c.get("p_country"),
        "city": c.get("p_city"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_client",
        description="Create a client in the authenticated FreshBooks account.",
    )
    parser.add_argument("--organization", default="", help="Company/organization name.")
    parser.add_argument("--first-name", dest="first_name", default="", help="Contact first name.")
    parser.add_argument("--last-name", dest="last_name", default="", help="Contact last name.")
    parser.add_argument("--email", default="", help="Contact email.")
    parser.add_argument(
        "--currency-code", dest="currency_code", default="USD", help="ISO currency code."
    )
    parser.add_argument("--phone", default="", help="Contact phone.")
    parser.add_argument("--city", default="", help="Billing city.")
    parser.add_argument("--country", default="", help="Billing country.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                organization=args.organization,
                first_name=args.first_name,
                last_name=args.last_name,
                email=args.email,
                currency_code=args.currency_code,
                phone=args.phone,
                city=args.city,
                country=args.country,
            )
        )
    except Exception as exc:
        print(f"create_client failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

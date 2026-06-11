#!/usr/bin/env python3
"""Skill operation: create_customer — create a Wave customer.

Runs through Tabby's POST /execute/fetch, i.e. fetch() inside the authenticated Wave browser session via GraphQL. See noui_runtime/wave_gql.py.
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

from noui_runtime.wave_gql import get_business_id, gql_input_errors, gql_request  # noqa: E402

_MUTATION = """
mutation ($input: CustomerCreateInput!) {
  customerCreate(input: $input) {
    didSucceed
    inputErrors { message path code }
    customer { id name email phone }
  }
}
"""


async def execute(name: str, email: str = "", phone: str = "") -> dict:
    business_id = await get_business_id()
    inp: dict = {"businessId": business_id, "name": name}
    if email:
        inp["email"] = email
    if phone:
        inp["phone"] = phone
    body = await gql_request(_MUTATION, {"input": inp})
    gql_input_errors(body, "customerCreate")
    c = ((body.get("data") or {}).get("customerCreate") or {}).get("customer") or {}
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "email": c.get("email"),
        "phone": c.get("phone"),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="create_customer")
    p.add_argument("--name", required=True)
    p.add_argument("--email", default="")
    p.add_argument("--phone", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(name=args.name, email=args.email, phone=args.phone))
    except Exception as exc:
        print(f"create_customer failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

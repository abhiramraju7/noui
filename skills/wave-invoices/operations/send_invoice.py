#!/usr/bin/env python3
"""Skill operation: send_invoice — email a Wave invoice to its customer."""

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
mutation ($input: InvoiceSendInput!) {
  invoiceSend(input: $input) {
    didSucceed
    inputErrors { message path }
    invoice { id status lastSentAt lastSentVia }
  }
}
"""


async def execute(
    invoice_id: str,
    to: str = "",
    subject: str = "",
    message: str = "",
    attach_pdf: bool = True,
) -> dict:
    await get_business_id()  # ensure session/business resolves
    to_list = [e.strip() for e in to.split(",") if e.strip()]
    if not to_list:
        inv_body = await gql_request(
            """
            query ($businessId: ID!, $invoiceId: ID!) {
              business(id: $businessId) {
                invoice(id: $invoiceId) { customer { email } }
              }
            }
            """,
            {"businessId": await get_business_id(), "invoiceId": invoice_id},
        )
        email = (
            (((inv_body.get("data") or {}).get("business") or {}).get("invoice") or {}).get(
                "customer"
            )
            or {}
        ).get("email")
        if email:
            to_list = [email]
    if not to_list:
        raise RuntimeError("No recipient: pass --to or set the customer email first.")

    inp: dict = {"invoiceId": invoice_id, "to": to_list, "attachPDF": attach_pdf}
    if subject:
        inp["subject"] = subject
    if message:
        inp["message"] = message

    body = await gql_request(_MUTATION, {"input": inp})
    gql_input_errors(body, "invoiceSend")
    inv = ((body.get("data") or {}).get("invoiceSend") or {}).get("invoice") or {}
    return {
        "invoice_id": invoice_id,
        "emailed": True,
        "status": inv.get("status"),
        "last_sent_at": inv.get("lastSentAt"),
        "last_sent_via": inv.get("lastSentVia"),
        "to": to_list,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="send_invoice")
    p.add_argument("--invoice-id", required=True)
    p.add_argument("--to", default="")
    p.add_argument("--subject", default="")
    p.add_argument("--message", default="")
    p.add_argument("--no-pdf", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice_id=args.invoice_id,
                to=args.to,
                subject=args.subject,
                message=args.message,
                attach_pdf=not args.no_pdf,
            )
        )
    except Exception as exc:
        print(f"send_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

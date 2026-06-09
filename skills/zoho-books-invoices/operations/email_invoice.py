#!/usr/bin/env python3
"""Skill operation: email_invoice

Email an invoice to its customer. Uses Zoho Books' default email content unless
overridden. Emailing a draft marks it as Sent. Writes data. Prints JSON.
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
    invoice_id: str,
    to: str = "",
    subject: str = "",
    body: str = "",
) -> dict:
    """Email an invoice.

    Args:
        invoice_id: Invoice id (from create_invoice / list_invoices).
        to: Recipient override (comma-separated). Defaults to the customer email.
        subject: Subject override (defaults to Zoho's template).
        body: Body override (defaults to Zoho's template).

    Returns:
        {invoice_id, emailed, message, to}
    """
    # Pull Zoho's default email content (recipients, subject, body) for this invoice.
    defaults = await books_request(f"invoices/{invoice_id}/email")
    dd = (defaults["body"] or {}).get("data") or {} if defaults["status"] == 200 else {}

    to_mail_ids = [e.strip() for e in to.split(",") if e.strip()]
    if not to_mail_ids:
        to_mail_ids = [c.get("email") for c in (dd.get("to_contacts") or []) if c.get("email")]
        to_mail_ids = [e for e in to_mail_ids if e]
    if not to_mail_ids:
        raise RuntimeError("No recipient: pass --to or set the customer's email first.")

    payload: dict = {
        "to_mail_ids": to_mail_ids,
        "subject": subject
        or dd.get("subject")
        or f"Invoice from {dd.get('organization_name', '')}".strip(),
        "body": body or dd.get("body") or "",
    }
    res = await books_request(f"invoices/{invoice_id}/email", method="POST", body=payload)
    rb = res["body"] or {}
    if res["status"] not in (200, 201) or rb.get("code") not in (0, None):
        raise RuntimeError(f"email_invoice failed ({res['status']}): {str(rb)[:300]}")
    return {
        "invoice_id": invoice_id,
        "emailed": True,
        "message": rb.get("message"),
        "to": to_mail_ids,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email_invoice", description="Email a Zoho Books invoice."
    )
    parser.add_argument("--invoice-id", dest="invoice_id", required=True, help="Invoice id.")
    parser.add_argument("--to", default="", help="Recipient override (comma-separated).")
    parser.add_argument("--subject", default="", help="Subject override.")
    parser.add_argument("--body", default="", help="Body override.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(invoice_id=args.invoice_id, to=args.to, subject=args.subject, body=args.body)
        )
    except Exception as exc:
        print(f"email_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

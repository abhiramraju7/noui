#!/usr/bin/env python3
"""Skill operation: send_invoice

Emails an invoice to the customer via the Xero Sales UI BFF:
``POST go.xero.com/api/invoicing/invoice/email?invoiceId=<id>`` — captured from a
live approve-and-send workflow recording. Pulls the default email template,
subject, body, and recipient from ``invoice/<id>/emailsettings`` and the invoice
itself, allowing optional overrides.

The invoice must be AUTHORISED (approved) before it can be emailed.

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

from noui_runtime.xero_invoicing import get_invoicing_headers, invoicing_fetch  # noqa: E402


def _fill_placeholders(text: str, kv: dict) -> str:
    if not text:
        return text
    for key, val in (kv or {}).items():
        if val is not None:
            text = text.replace(key, str(val))
    return text


async def _email_defaults(headers: dict, invoice_id: str) -> dict:
    """Resolve default subject/body/template/recipient for an invoice email."""
    res = await invoicing_fetch(f"invoice/{invoice_id}/emailsettings")
    if res.get("status") != 200 or not res.get("body"):
        return {}
    settings = json.loads(res["body"])
    templates = settings.get("EmailTemplates") or []
    default_id = settings.get("DefaultTemplateId")
    template = next(
        (t for t in templates if t.get("EmailTemplateId") == default_id),
        templates[0] if templates else {},
    )
    body_kv = settings.get("BodyPlaceholderKeyValues") or {}
    subject = _fill_placeholders(template.get("Subject", ""), body_kv)
    content = _fill_placeholders(template.get("Content", ""), body_kv)
    return {
        "template_id": template.get("EmailTemplateId"),
        "subject": subject,
        "message": content,
        "contact_name": body_kv.get("[Contact Name]") or "",
    }


async def _recipient(headers: dict, invoice_id: str) -> dict:
    res = await invoicing_fetch(f"invoice/find/{invoice_id}")
    if res.get("status") != 200 or not res.get("body"):
        return {}
    inv = json.loads(res["body"])
    cust = inv.get("Customer") or {}
    return {"address": cust.get("Email"), "name": cust.get("Name") or " "}


async def execute(
    invoice_id: str,
    to: str | None = None,
    subject: str | None = None,
    message: str | None = None,
    attach_pdf: bool = True,
    send_me_a_copy: bool = False,
) -> dict:
    """Email an approved invoice to its customer.

    Args:
        invoice_id: The invoice id (from create_invoice / list_invoices).
        to: Optional recipient email override.
        subject: Optional subject override.
        message: Optional HTML/plain message override.
        attach_pdf: Attach the invoice PDF (default True).
        send_me_a_copy: Send the org a copy (default False).

    Returns:
        {invoice_id, sent, to, subject}
    """
    headers = await get_invoicing_headers()

    defaults = await _email_defaults(headers, invoice_id)
    recipient = await _recipient(headers, invoice_id)

    to_addr = to or recipient.get("address")
    if not to_addr:
        raise RuntimeError("No recipient email found on the invoice; pass --to explicitly.")
    final_subject = subject or defaults.get("subject") or "Invoice from your supplier"
    final_message = message or defaults.get("message") or ""
    # The BFF expects HTML; wrap plain text overrides.
    if message and "<" not in message:
        final_message = f"<p>{message}</p>"

    body = {
        "attachPDF": attach_pdf,
        "bcc": [],
        "cc": [],
        "includeFiles": False,
        "message": final_message,
        "selectedTemplateID": defaults.get("template_id"),
        "sendMeACopy": send_me_a_copy,
        "subject": final_subject,
        "to": [{"address": to_addr, "name": recipient.get("name") or " "}],
    }

    path = f"invoice/email?invoiceId={invoice_id}"
    res = await invoicing_fetch(path, method="POST", body=body, headers=headers)
    if res.get("status") in (401, 403):
        headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(path, method="POST", body=body, headers=headers)

    if res.get("status") not in (200, 201, 204):
        raise RuntimeError(
            f"invoice/email returned {res.get('status')}: {str(res.get('body'))[:400]}"
        )

    return {
        "invoice_id": invoice_id,
        "sent": True,
        "to": to_addr,
        "subject": final_subject,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="send_invoice",
        description="Email an approved Xero invoice to its customer.",
    )
    parser.add_argument("--invoice-id", required=True, dest="invoice_id", help="Invoice id.")
    parser.add_argument("--to", help="Recipient email override.")
    parser.add_argument("--subject", help="Subject override.")
    parser.add_argument("--message", help="Message override (plain or HTML).")
    parser.add_argument(
        "--no-pdf", action="store_false", dest="attach_pdf", help="Do not attach the PDF."
    )
    parser.add_argument(
        "--copy-me", action="store_true", dest="send_me_a_copy", help="Send the org a copy."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice_id=args.invoice_id,
                to=args.to,
                subject=args.subject,
                message=args.message,
                attach_pdf=args.attach_pdf,
                send_me_a_copy=args.send_me_a_copy,
            )
        )
    except Exception as exc:
        print(f"send_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Skill operation: mark_payment

Records a payment against an existing FreshBooks invoice, marking it paid (or
partially paid). The invoice is given by its invoice number (e.g. "0000001") or
numeric id and resolved automatically; the payment amount defaults to the invoice's
full outstanding balance. Runs inside Tabby's authenticated browser via CDP using a
sniffed in-memory bearer token. See noui_runtime/freshbooks_auth.py.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.cdp import cdp_eval, find_page  # noqa: E402
from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_auth import get_bearer  # noqa: E402

API_BASE = "https://api.freshbooks.com"
PAGE_MATCH = "my.freshbooks.com"
API_VERSION = "2023-02-20"

# FreshBooks-accepted payment method labels.
PAYMENT_TYPES = {
    "check": "Check",
    "cash": "Cash",
    "credit": "Credit",
    "credit card": "Credit Card",
    "bank transfer": "Bank Transfer",
    "ach": "ACH",
    "paypal": "PayPal",
    "other": "Other",
}


def _money(node: dict | None) -> str:
    return ((node or {}).get("amount")) or "0.00"


async def _api(
    ws_url: str, bearer: str, account_id: str, method: str, path: str, body: dict | None = None
) -> dict:
    url = f"{API_BASE}/accounting/account/{account_id}/{path}"
    init = {
        "method": method,
        "credentials": "omit",
        "headers": {
            "Authorization": bearer,
            "X-API-VERSION": API_VERSION,
            "X-Account-ID": account_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    }
    if body is not None:
        init["body"] = json.dumps(body)
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)


async def _resolve_invoice(ws_url: str, bearer: str, account_id: str, invoice: str) -> dict:
    """Resolve an invoice number/id to its invoice record (with outstanding balance)."""
    res = await _api(ws_url, bearer, account_id, "GET", "invoices/invoices?per_page=100")
    invoices = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "invoices", []
    )
    target = invoice.strip().lstrip("#")
    target_digits = target.lstrip("0") or "0"
    for inv in invoices:
        num = str(inv.get("invoice_number") or "")
        if str(inv.get("id")) == target or num == target or num.lstrip("0") == target_digits:
            return inv
    available = ", ".join(str(i.get("invoice_number")) for i in invoices[:15])
    raise ValueError(f"No invoice matching {invoice!r}. Recent invoices: {available}")


async def execute(
    invoice: str,
    amount: float | None = None,
    payment_type: str = "Check",
    date: str | None = None,
    note: str = "",
    currency_code: str = "USD",
) -> dict:
    """Record a payment against an invoice.

    Args:
        invoice: Invoice number (e.g. "0000001") or numeric id.
        amount: Payment amount; defaults to the invoice's full outstanding balance.
        payment_type: Payment method (Check, Cash, Credit, Bank Transfer, etc.).
        date: Payment date YYYY-MM-DD (defaults to today).
        note: Optional note recorded on the payment.
        currency_code: ISO currency code (default USD).

    Returns:
        {payment_id, invoice_number, client, amount, currency, payment_type, date,
         invoice_status, invoice_outstanding}
    """
    date = date or _dt.date.today().isoformat()
    method_label = PAYMENT_TYPES.get(payment_type.strip().lower(), payment_type)

    ws_url = await find_page(PAGE_MATCH)
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run "
            "`tabby session ensure --profile freshbooks` and open my.freshbooks.com."
        )

    bearer = await get_bearer()
    account_id = await get_account_id(ws_url, bearer)
    try:
        inv = await _resolve_invoice(ws_url, bearer, account_id, invoice)
    except ValueError:
        bearer = await get_bearer(force=True)
        inv = await _resolve_invoice(ws_url, bearer, account_id, invoice)

    outstanding = (
        _money(inv.get("outstanding")) if isinstance(inv.get("outstanding"), dict) else None
    )
    pay_amount = amount if amount is not None else float(outstanding or _money(inv.get("amount")))

    body = {
        "payment": {
            "invoiceid": inv.get("id"),
            "amount": {"amount": f"{float(pay_amount):.2f}", "code": currency_code},
            "date": date,
            "type": method_label,
            "note": note,
        }
    }

    res = await _api(ws_url, bearer, account_id, "POST", "payments/payments", body)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        res = await _api(ws_url, bearer, account_id, "POST", "payments/payments", body)

    if res.get("status") not in (200, 201):
        raise RuntimeError(
            f"FreshBooks create payment returned {res.get('status')}: {str(res.get('body'))[:300]}"
        )

    pay = (((json.loads(res["body"]) or {}).get("response") or {}).get("result") or {}).get(
        "payment", {}
    )

    # Re-read the invoice to report the post-payment status.
    refreshed = await _resolve_invoice(ws_url, bearer, account_id, invoice)
    amt = pay.get("amount") or {}
    client = (
        refreshed.get("current_organization")
        or refreshed.get("organization")
        or f"{refreshed.get('fname', '')} {refreshed.get('lname', '')}".strip()
    )
    return {
        "payment_id": pay.get("id"),
        "invoice_number": refreshed.get("invoice_number"),
        "client": client,
        "amount": amt.get("amount"),
        "currency": amt.get("code"),
        "payment_type": pay.get("type"),
        "date": pay.get("date"),
        "invoice_status": refreshed.get("v3_status") or refreshed.get("display_status"),
        "invoice_outstanding": _money(refreshed.get("outstanding"))
        if isinstance(refreshed.get("outstanding"), dict)
        else None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mark_payment",
        description="Record a payment against a FreshBooks invoice (marks it paid).",
    )
    parser.add_argument("--invoice", required=True, help="Invoice number (e.g. 0000001) or id.")
    parser.add_argument(
        "--amount",
        type=float,
        default=None,
        help="Payment amount; defaults to the invoice's full outstanding balance.",
    )
    parser.add_argument(
        "--type",
        dest="payment_type",
        default="Check",
        help="Payment method: Check, Cash, Credit, Bank Transfer, PayPal, Other.",
    )
    parser.add_argument("--date", default=None, help="Payment date YYYY-MM-DD (default today).")
    parser.add_argument("--note", default="", help="Optional note on the payment.")
    parser.add_argument(
        "--currency-code", dest="currency_code", default="USD", help="ISO currency code."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice=args.invoice,
                amount=args.amount,
                payment_type=args.payment_type,
                date=args.date,
                note=args.note,
                currency_code=args.currency_code,
            )
        )
    except Exception as exc:
        print(f"mark_payment failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Skill operation: mark_payment

Records a payment against an invoice via the Xero accounting API:
``PUT api.xero.com/api.xro/2.0/payments`` — captured from a live mark-payment
workflow recording. The deposit account is resolved from the invoicing
``account/payable`` BFF list by name or code.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import date
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.cdp import cdp_eval  # noqa: E402
from noui_runtime.xero_account import get_tenant  # noqa: E402
from noui_runtime.xero_auth import get_bearer  # noqa: E402
from noui_runtime.xero_invoicing import get_invoicing_headers, invoicing_fetch  # noqa: E402

API_BASE = "https://api.xero.com/api.xro/2.0"
PAGE_MATCH = "go.xero.com"


def _xero_date(d: date) -> str:
    return d.strftime("%d %b %Y")


async def _resolve_account(ws_url: str, headers: dict, account: str) -> dict:
    """Resolve a deposit account (by id, code, or name) from account/payable."""
    res = await invoicing_fetch(ws_url, headers, "account/payable")
    accounts = json.loads(res["body"]) if res.get("status") == 200 and res.get("body") else []
    needle = account.strip().lower()
    for a in accounts:
        if (a.get("Id") or "").lower() == needle:
            return a
    for a in accounts:
        if (a.get("Code") or "").lower() == needle or (a.get("Name") or "").lower() == needle:
            return a
    matches = [a for a in accounts if needle in (a.get("Name") or "").lower()]
    if matches:
        return matches[0]
    raise RuntimeError(
        f"No payable account matching {account!r}. "
        f"Available: {', '.join((a.get('Name') or '') for a in accounts[:8])}"
    )


async def _put_payment(
    ws_url: str, bearer: str, tenant_id: str, shortcode: str, payment: dict
) -> dict:
    url = f"{API_BASE}/payments"
    init = {
        "method": "PUT",
        "credentials": "omit",
        "headers": {
            "Authorization": bearer,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "xero-tenant-id": tenant_id,
            "xero-tenant-shortcode": shortcode,
            "xero-shell-app-name": "Invoicing",
            "xero-correlation-id": str(uuid.uuid4()),
        },
        "body": json.dumps({"Payments": [payment]}),
    }
    js = (
        f"fetch({json.dumps(url)}, {json.dumps(init)}).then("
        "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
    )
    return await cdp_eval(ws_url, js)


async def execute(
    invoice_id: str,
    amount: float,
    account: str,
    payment_date: str | None = None,
    reference: str = "",
) -> dict:
    """Record a payment against an invoice.

    Args:
        invoice_id: The invoice id to pay (must be AUTHORISED).
        amount: Payment amount.
        account: Deposit account id, code, or name (resolved via account/payable).
        payment_date: Optional date YYYY-MM-DD (default today).
        reference: Optional payment reference.

    Returns:
        {invoice_id, payment_id, amount, account, date, status}
    """
    ws_url, headers = await get_invoicing_headers()
    acct = await _resolve_account(ws_url, headers, account)

    bearer = await get_bearer()
    tenant_id, shortcode = await get_tenant(ws_url, bearer)

    pay_date = date.fromisoformat(payment_date) if payment_date else date.today()
    payment = {
        "Invoice": {"InvoiceID": invoice_id},
        "Account": {"AccountID": acct.get("Id")},
        "Date": _xero_date(pay_date),
        "Amount": f"{amount:.2f}",
        "Reference": reference,
        "CurrencyRate": None,
    }

    res = await _put_payment(ws_url, bearer, tenant_id, shortcode, payment)
    if res.get("status") in (401, 403):
        bearer = await get_bearer(force=True)
        tenant_id, shortcode = await get_tenant(ws_url, bearer, force=True)
        res = await _put_payment(ws_url, bearer, tenant_id, shortcode, payment)

    if res.get("status") not in (200, 201):
        raise RuntimeError(
            f"payments PUT returned {res.get('status')}: {str(res.get('body'))[:400]}"
        )

    data = json.loads(res["body"]) if res.get("body") else {}
    payments = data.get("Payments") or []
    pid = payments[0].get("PaymentID") if payments else None
    pstatus = payments[0].get("Status") if payments else None

    return {
        "invoice_id": invoice_id,
        "payment_id": pid,
        "amount": f"{amount:.2f}",
        "account": acct.get("Name"),
        "date": _xero_date(pay_date),
        "status": pstatus or "OK",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mark_payment",
        description="Record a payment against a Xero invoice.",
    )
    parser.add_argument("--invoice-id", required=True, dest="invoice_id", help="Invoice id.")
    parser.add_argument("--amount", required=True, type=float, help="Payment amount.")
    parser.add_argument(
        "--account", required=True, help="Deposit account id, code, or name."
    )
    parser.add_argument("--date", dest="payment_date", help="Payment date YYYY-MM-DD.")
    parser.add_argument("--reference", default="", help="Optional payment reference.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                invoice_id=args.invoice_id,
                amount=args.amount,
                account=args.account,
                payment_date=args.payment_date,
                reference=args.reference,
            )
        )
    except Exception as exc:
        print(f"mark_payment failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Skill operation: create_invoice

Creates a draft invoice via the Xero Sales UI BFF:
``POST go.xero.com/api/invoicing/invoice/create`` — captured from a live
create-invoice workflow recording.

Prints JSON on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from noui_runtime.xero_invoicing import get_invoicing_headers, invoicing_fetch  # noqa: E402

DEFAULT_BRANDING_THEME = "abe6b1c3-4c44-4fda-a4af-e958f2864a63"
DEFAULT_ACCOUNT_CODE = "200"
DEFAULT_TAX_TYPE = "OUTPUT"


def _xero_date(d: date) -> str:
    return d.strftime("%Y %b %d")


def _line_item(
    description: str,
    quantity: float,
    unit_price: float,
    account_code: str,
    tax_type: str,
) -> dict:
    amount = quantity * unit_price
    return {
        "accountCode": {"value": account_code},
        "amount": {"value": f"{amount:.2f}"},
        "description": {"value": description},
        "discountRate": {"value": ""},
        "itemCode": {"value": ""},
        "itemId": {"value": ""},
        "itemOrder": {"value": 0},
        "lineItemId": "",
        "linkedTransactionId": "",
        "projectId": "",
        "quantity": str(quantity),
        "salesTaxCodeId": None,
        "taxAmount": "0.00",
        "taxType": tax_type,
        "tracking": [],
        "unitPrice": {"value": f"{unit_price:.2f}"},
    }


def _customer_label(c: dict) -> str:
    return (c.get("Name") or c.get("name") or "").strip()


def _customer_for_create(c: dict) -> dict:
    """Map customer/find (PascalCase) to invoice/create body (camelCase)."""
    people = c.get("People") or c.get("people") or []
    phone = c.get("Phone") or {}
    mobile = c.get("MobilePhone") or {}
    due = c.get("InvoicePaymentTerm") or c.get("defaultInvoiceDueDate") or {}
    return {
        "balances": {"outstanding": 0, "overdue": 0},
        "creditMonitoring": {
            "creditLimitAmount": None,
            "creditHold": False,
            "creditLimitStatus": "Inactive",
        },
        "defaultInvoiceBrandingThemeId": c.get("BrandingThemeId"),
        "defaultInvoiceCurrencyCode": c.get("CurrencyCode"),
        "discount": c.get("Discount") or "",
        "email": c.get("Email") or c.get("email"),
        "id": c.get("Id") or c.get("id"),
        "name": _customer_label(c),
        "people": [
            {
                "name": p.get("Name") or p.get("name"),
                "email": p.get("Email") or p.get("email"),
                "isPrimary": p.get("IsPrimary", p.get("isPrimary")),
                "isIncludedInEmails": p.get("IsIncludedInEmails", p.get("isIncludedInEmails")),
            }
            for p in people
        ],
        "shouldUseDefaults": True,
        "showDeliveryAddress": False,
        "taxRate": c.get("TaxRate"),
        "accountCode": c.get("AccountCode"),
        "accountNumber": c.get("AccountNumber"),
        "defaultInvoiceDueDate": {"day": due.get("Day"), "type": due.get("Type")},
        "firstName": c.get("FirstName"),
        "lastName": c.get("LastName"),
        "phone": {
            "areaCode": phone.get("AreaCode", ""),
            "countryCode": phone.get("CountryCode", ""),
            "number": phone.get("Number", ""),
            "type": phone.get("Type", "Default"),
        },
        "mobilePhone": {
            "areaCode": mobile.get("AreaCode", ""),
            "countryCode": mobile.get("CountryCode", ""),
            "number": mobile.get("Number", ""),
            "type": mobile.get("Type", "Mobile"),
        },
        "taxBasis": c.get("TaxBasis"),
        "tracking": c.get("Tracking") or [],
        "address": None,
        "addresses": c.get("Addresses") or [],
    }


async def _find_customer(ws_url: str, headers: dict, name: str) -> tuple[dict, str, dict]:
    needle = name.strip().lower()
    ctx = {"ws_url": ws_url, "headers": headers}

    async def _fetch(q: str) -> list:
        params = urllib.parse.urlencode({"page": 1, "q": q})
        res = await invoicing_fetch(ctx["ws_url"], ctx["headers"], f"customer/find?{params}")
        if res.get("status") in (401, 403):
            ctx["ws_url"], ctx["headers"] = await get_invoicing_headers(force=True)
            res = await invoicing_fetch(ctx["ws_url"], ctx["headers"], f"customer/find?{params}")
        if res.get("status") != 200:
            raise RuntimeError(
                f"customer/find returned {res.get('status')}: {str(res.get('body'))[:300]}"
            )
        return json.loads(res["body"]) if res.get("body") else []

    customers = await _fetch(name)
    if not customers:
        customers = await _fetch("")
    exact = [c for c in customers if _customer_label(c).lower() == needle]
    matches = exact or [c for c in customers if needle in _customer_label(c).lower()]
    if not matches:
        raise RuntimeError(f"No customer matching {name!r}. Use list_invoice_customers first.")
    return _customer_for_create(matches[0]), ctx["ws_url"], ctx["headers"]


async def _branding_theme(ws_url: str, headers: dict) -> str:
    res = await invoicing_fetch(ws_url, headers, "branding/find")
    if res.get("status") == 200 and res.get("body"):
        themes = json.loads(res["body"])
        if themes:
            return themes[0].get("id") or themes[0].get("brandingThemeId") or DEFAULT_BRANDING_THEME
    return DEFAULT_BRANDING_THEME


async def execute(
    customer: str,
    description: str,
    quantity: float = 1.0,
    unit_price: float = 0.0,
    account_code: str = DEFAULT_ACCOUNT_CODE,
    tax_type: str = DEFAULT_TAX_TYPE,
    invoice_date: str | None = None,
    due_date: str | None = None,
    approve: bool = False,
) -> dict:
    """Create an invoice for a customer (draft, or approved/AUTHORISED).

    Args:
        customer: Customer name (resolved via customer/find).
        description: Line item description.
        quantity: Line item quantity.
        unit_price: Line item unit price.
        account_code: Sales account code (default 200).
        tax_type: Tax type on line (default OUTPUT).
        invoice_date: Optional date YYYY-MM-DD (default today).
        due_date: Optional due date YYYY-MM-DD (default today + 7 days).
        approve: If True, create directly as AUTHORISED (approved) instead of DRAFT.

    Returns:
        {id, number, status, customer, total, currency}
    """
    ws_url, headers = await get_invoicing_headers()
    cust, ws_url, headers = await _find_customer(ws_url, headers, customer)
    theme = await _branding_theme(ws_url, headers)

    inv_date = date.fromisoformat(invoice_date) if invoice_date else date.today()
    due = date.fromisoformat(due_date) if due_date else inv_date + timedelta(days=7)
    status = "AUTHORISED" if approve else "DRAFT"

    body = {
        "brandingThemeId": theme,
        "currencyCode": "INR",
        "currencyRate": 1,
        "customer": cust,
        "date": _xero_date(inv_date),
        "displayDeliveryAddress": False,
        "dueDate": _xero_date(due),
        "id": "",
        "lineItems": [_line_item(description, quantity, unit_price, account_code, tax_type)],
        "number": "",
        "organisationCurrencyRateId": "",
        "payments": [],
        "providerCurrencyRateId": "",
        "reference": {"value": ""},
        "salesTaxExemptionReasonCode": None,
        "sent": False,
        "status": status,
        "taxType": "EXCLUSIVE",
    }

    res = await invoicing_fetch(ws_url, headers, "invoice/create", method="POST", body=body)
    if res.get("status") in (401, 403):
        ws_url, headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(ws_url, headers, "invoice/create", method="POST", body=body)

    if res.get("status") not in (200, 201):
        raise RuntimeError(
            f"invoice/create returned {res.get('status')}: {str(res.get('body'))[:400]}"
        )

    # DRAFT create returns an empty body; AUTHORISED returns the full invoice
    # (PascalCase). Parse both, then fall back to latest endpoints for the id.
    created = json.loads(res["body"]) if res.get("body") else {}
    invoice_id = created.get("Id") or created.get("id") or created.get("invoiceId")
    number = created.get("Number") or created.get("number")
    totals = created.get("Totals") or {}
    total = created.get("total") or totals.get("Total")

    if not invoice_id:
        # AUTHORISED is rejected by latest/status; use invoice/latest (most recent).
        if approve:
            latest_res = await invoicing_fetch(ws_url, headers, "invoice/latest")
            if latest_res.get("status") == 200 and latest_res.get("body"):
                arr = json.loads(latest_res["body"])
                if isinstance(arr, list) and arr:
                    invoice_id = arr[0].get("Id")
                    number = number or arr[0].get("Number")
        else:
            latest_res = await invoicing_fetch(ws_url, headers, "invoice/latest/status/DRAFT")
            if latest_res.get("status") == 200 and latest_res.get("body"):
                ltxt = latest_res["body"].strip().strip('"')
                if ltxt and ltxt != "null":
                    invoice_id = ltxt

    return {
        "id": invoice_id,
        "number": number,
        "status": status,
        "customer": cust.get("name") or customer,
        "total": total,
        "currency": "INR",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_invoice",
        description="Create a draft invoice via the Xero Sales/Invoicing BFF.",
    )
    parser.add_argument("--customer", required=True, help="Customer name.")
    parser.add_argument("--description", required=True, help="Line item description.")
    parser.add_argument("--quantity", type=float, default=1.0)
    parser.add_argument("--unit-price", type=float, default=0.0, dest="unit_price")
    parser.add_argument("--account-code", default=DEFAULT_ACCOUNT_CODE, dest="account_code")
    parser.add_argument("--invoice-date", dest="invoice_date", help="YYYY-MM-DD")
    parser.add_argument("--due-date", dest="due_date", help="YYYY-MM-DD")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Create as AUTHORISED (approved) instead of DRAFT.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(
            execute(
                customer=args.customer,
                description=args.description,
                quantity=args.quantity,
                unit_price=args.unit_price,
                account_code=args.account_code,
                invoice_date=args.invoice_date,
                due_date=args.due_date,
                approve=args.approve,
            )
        )
    except Exception as exc:
        print(f"create_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

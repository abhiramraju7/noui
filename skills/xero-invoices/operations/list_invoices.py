#!/usr/bin/env python3
"""Skill operation: list_invoices

Lists invoices from the Xero Sales/Invoicing UI using the same BFF endpoint the
page calls: ``GET go.xero.com/api/invoicing/invoice/find``. Runs inside Tabby's
authenticated browser via CDP with sniffed Sales/Invoicing headers.
See noui_runtime/xero_invoicing.py.

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

# Matches the status tabs on the Sales > Invoices page.
STATUSES = ("ALL", "DRAFT", "AWAITING APPROVAL", "AWAITING PAYMENT", "PAID", "REPEATING")


async def execute(status: str = "ALL", page: int = 1) -> dict:
    """List invoices for the authenticated Xero organisation.

    Args:
        status: Invoice status tab (ALL, DRAFT, AWAITING PAYMENT, PAID, etc.).
        page: 1-based page number.

    Returns:
        {count, page, status, invoices: [{id, number, contact, status, total, currency, date}]}
    """
    ws_url, headers = await get_invoicing_headers()
    path = f"invoice/find?page={page}&status={status}"
    res = await invoicing_fetch(ws_url, headers, path)
    if res.get("status") in (401, 403):
        ws_url, headers = await get_invoicing_headers(force=True)
        res = await invoicing_fetch(ws_url, headers, path)

    body = res.get("body", "")

    # On some orgs invoice/find returns 404 "object is NULL" even when drafts exist.
    # Fall back to the invoice/latest/status endpoints the create form uses.
    if res.get("status") == 404 and "NULL" in body:
        return await _list_via_latest(ws_url, headers, status)
    if res.get("status") != 200:
        raise RuntimeError(
            f"Xero invoice/find returned {res.get('status')}: {str(body)[:300]}"
        )

    raw = json.loads(body) if body else []
    if isinstance(raw, dict):
        raw = raw.get("Items") or raw.get("Invoices") or raw.get("items") or []

    invoices = []
    for inv in raw:
        contact = inv.get("Contact") or {}
        invoices.append(
            {
                "id": inv.get("Id") or inv.get("InvoiceID"),
                "number": inv.get("InvoiceNumber") or inv.get("Number"),
                "contact": contact.get("Name") or inv.get("ContactName"),
                "status": inv.get("Status"),
                "total": inv.get("Total") or inv.get("AmountDue"),
                "currency": inv.get("CurrencyCode"),
                "date": inv.get("Date") or inv.get("DateString"),
            }
        )

    return {"count": len(invoices), "page": page, "status": status, "invoices": invoices}


# invoice/latest/status only supports these tabs in the new SPA.
_LATEST_STATUSES = ("DRAFT", "SUBMITTED")


async def _list_via_latest(ws_url, headers, status: str) -> dict:
    """Fallback: surface the latest invoice id per status via invoice/latest.

    The new invoicing SPA exposes only ``invoice/latest`` (most recent overall)
    and ``invoice/latest/status/<STATUS>`` (most recent of a status). This yields
    at least the newest invoice id when invoice/find reports an empty object.
    """
    statuses = _LATEST_STATUSES if status == "ALL" else (status.upper(),)
    invoices: list[dict] = []
    seen: set[str] = set()
    for st in statuses:
        if st not in _LATEST_STATUSES:
            continue
        res = await invoicing_fetch(ws_url, headers, f"invoice/latest/status/{st}")
        if res.get("status") != 200:
            continue
        inv_id = (res.get("body") or "").strip().strip('"')
        if inv_id and inv_id != "null" and inv_id not in seen:
            seen.add(inv_id)
            invoices.append({"id": inv_id, "status": st, "number": None,
                             "contact": None, "total": None, "currency": None, "date": None})

    return {
        "count": len(invoices),
        "page": 1,
        "status": status,
        "invoices": invoices,
        "note": "invoice/find returned empty; ids surfaced via invoice/latest/status",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list_invoices",
        description="List invoices from the Xero Sales/Invoicing page API.",
    )
    parser.add_argument(
        "--status", default="ALL",
        help="Status tab: ALL, DRAFT, AWAITING PAYMENT, PAID, etc.",
    )
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(status=args.status, page=args.page))
    except Exception as exc:
        print(f"list_invoices failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

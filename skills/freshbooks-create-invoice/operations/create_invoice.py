#!/usr/bin/env python3
"""Skill operation: create_invoice

Creates a new invoice for the authenticated FreshBooks account, optionally
finalizing it (marking it as Sent) in the same call. Runs through Tabby's
POST /execute/fetch, i.e. fetch() inside the authenticated FreshBooks browser
session, so the session's own auth is applied by the browser and no token is
sniffed or passed from Python. See noui_runtime/freshbooks_api.py.

The client is given by name (organization or person) and resolved to a FreshBooks
customer id, so callers never need to know internal ids. A single line item can be
supplied with simple flags, or multiple lines via --lines-json.

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

from noui_runtime.freshbooks_account import get_account_id  # noqa: E402
from noui_runtime.freshbooks_api import fb_request  # noqa: E402


def _client_label(c: dict) -> str:
    org = (c.get("organization") or "").strip()
    person = f"{c.get('fname', '')} {c.get('lname', '')}".strip()
    return org or person or f"client {c.get('id')}"


async def _api(account_id: str, method: str, path: str, body: dict | None = None) -> dict:
    return await fb_request(
        f"/accounting/account/{account_id}/{path}",
        method=method,
        account_id=account_id,
        body=body,
    )


async def _resolve_client(account_id: str, client: str) -> dict:
    """Resolve a client name/organization to a FreshBooks client record."""
    data = await _api(account_id, "GET", "users/clients?per_page=100")
    clients = (((data or {}).get("response") or {}).get("result") or {}).get("clients", [])
    needle = client.strip().lower()
    # exact match on organization or full name first, then substring
    exact = [c for c in clients if _client_label(c).lower() == needle]
    matches = exact or [c for c in clients if needle in _client_label(c).lower()]
    if not matches:
        available = ", ".join(sorted(_client_label(c) for c in clients)) or "(none)"
        raise ValueError(f"No client matching {client!r}. Available clients: {available}")
    if len(matches) > 1:
        labels = ", ".join(_client_label(c) for c in matches)
        raise ValueError(f"Client {client!r} is ambiguous; matches: {labels}")
    return matches[0]


def _build_line(name: str, qty, unit_cost, description: str, tax_name: str, tax_rate) -> dict:
    line = {
        "name": name,
        "description": description or "",
        "qty": str(qty),
        "unit_cost": {"amount": f"{float(unit_cost):.2f}", "code": "USD"},
    }
    if tax_name:
        line["taxName1"] = tax_name
        line["taxAmount1"] = str(tax_rate)
    return line


async def execute(
    client: str,
    name: str = "",
    qty: float = 1,
    unit_cost: float | None = None,
    description: str = "",
    tax_name: str = "",
    tax_rate: float = 0,
    lines: list[dict] | None = None,
    create_date: str | None = None,
    currency_code: str = "USD",
    send: bool = False,
) -> dict:
    """Create an invoice for a client.

    Args:
        client: Client name or organization (resolved to a FreshBooks customer id).
        name: Line-item name/service (single-line mode).
        qty: Quantity for the single line item.
        unit_cost: Unit price for the single line item.
        description: Optional line description (single-line mode).
        tax_name: Optional tax label applied to the single line (e.g. "Sales Tax").
        tax_rate: Tax percent for tax_name (e.g. 8 for 8%).
        lines: Optional list of fully-formed line dicts (overrides single-line flags).
        create_date: Invoice date YYYY-MM-DD (defaults to today).
        currency_code: ISO currency code (default USD).
        send: If True, mark the invoice as Sent after creation.

    Returns:
        {id, invoice_number, client, amount, currency, status, create_date}
    """
    if lines is None:
        if not name or unit_cost is None:
            raise ValueError(
                "Provide either --lines-json or a single line (--name and --unit-cost)."
            )
        lines = [_build_line(name, qty, unit_cost, description, tax_name, tax_rate)]

    create_date = create_date or _dt.date.today().isoformat()

    account_id = await get_account_id()
    client_rec = await _resolve_client(account_id, client)

    body = {
        "invoice": {
            "customerid": client_rec.get("id"),
            "create_date": create_date,
            "currency_code": currency_code,
            "lines": lines,
        }
    }

    data = await _api(account_id, "POST", "invoices/invoices", body)
    inv = (((data or {}).get("response") or {}).get("result") or {}).get("invoice", {})

    if send and inv.get("id"):
        mark = await _api(
            account_id,
            "PUT",
            f"invoices/invoices/{inv['id']}",
            {"invoice": {"action_mark_as_sent": True}},
        )
        inv = (((mark or {}).get("response") or {}).get("result") or {}).get("invoice", inv)

    amount = inv.get("amount") or {}
    return {
        "id": inv.get("id"),
        "invoice_number": inv.get("invoice_number"),
        "client": _client_label(client_rec),
        "amount": amount.get("amount"),
        "currency": amount.get("code"),
        "status": inv.get("v3_status") or inv.get("display_status"),
        "create_date": inv.get("create_date"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_invoice",
        description="Create (and optionally send) a FreshBooks invoice for a client.",
    )
    parser.add_argument("--client", required=True, help="Client name or organization.")
    parser.add_argument("--name", default="", help="Line-item name/service (single-line mode).")
    parser.add_argument("--qty", type=float, default=1, help="Quantity (single-line mode).")
    parser.add_argument(
        "--unit-cost", dest="unit_cost", type=float, help="Unit price (single-line mode)."
    )
    parser.add_argument("--description", default="", help="Line description (single-line mode).")
    parser.add_argument(
        "--tax-name", dest="tax_name", default="", help="Tax label, e.g. 'Sales Tax'."
    )
    parser.add_argument(
        "--tax-rate", dest="tax_rate", type=float, default=0, help="Tax percent, e.g. 8."
    )
    parser.add_argument(
        "--lines-json",
        dest="lines_json",
        default="",
        help="JSON array of full line dicts; overrides single-line flags.",
    )
    parser.add_argument(
        "--create-date", dest="create_date", default=None, help="Invoice date YYYY-MM-DD."
    )
    parser.add_argument(
        "--currency-code", dest="currency_code", default="USD", help="ISO currency code."
    )
    parser.add_argument(
        "--send", action="store_true", help="Mark the invoice as Sent after creating it."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    lines = json.loads(args.lines_json) if args.lines_json else None
    try:
        result = asyncio.run(
            execute(
                client=args.client,
                name=args.name,
                qty=args.qty,
                unit_cost=args.unit_cost,
                description=args.description,
                tax_name=args.tax_name,
                tax_rate=args.tax_rate,
                lines=lines,
                create_date=args.create_date,
                currency_code=args.currency_code,
                send=args.send,
            )
        )
    except Exception as exc:
        print(f"create_invoice failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and "error" in result:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

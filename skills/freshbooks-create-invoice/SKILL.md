---
name: freshbooks-create-invoice
description: "Create a new invoice in FreshBooks for a client, with line items and optional tax, and optionally finalize it (mark as Sent). Use when the user wants to create/draft/issue/send an invoice or bill a client in FreshBooks. Writes data. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — Create Invoice

Creates an invoice for the authenticated FreshBooks account. The single operation
under `operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP.
The FreshBooks accounting API (`api.freshbooks.com`) authenticates with a short-lived
in-memory **bearer token** (not cookies) and serves wildcard CORS, so the operation
sniffs the live bearer off a real request via CDP `Network` events and replays the call
with `credentials:'omit'`. The token is cached on disk until shortly before its JWT
`exp`. See `noui_runtime/freshbooks_auth.py`.

The client is given **by name** (organization or person) and resolved to a FreshBooks
customer id automatically, so callers never need internal ids.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop via `chrome://inspect` (`localhost:9222`).
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.
3. The client must already exist in FreshBooks (matched by name/organization).

## Operation

### create_invoice — create (and optionally send) an invoice

```bash
# Draft: one line, 2 units @ $150, 8% Sales Tax
.venv/bin/python operations/create_invoice.py \
  --client "d1" --name "Consulting" --qty 2 --unit-cost 150 \
  --tax-name "Sales Tax" --tax-rate 8

# Create AND finalize (mark as Sent) in one call
.venv/bin/python operations/create_invoice.py \
  --client "Amazon" --name "Hosting" --qty 1 --unit-cost 500 \
  --tax-name "Sales Tax" --tax-rate 8 --send

# Multiple line items via JSON (overrides single-line flags)
.venv/bin/python operations/create_invoice.py --client "d1" --send \
  --lines-json '[{"name":"Design","qty":"10","unit_cost":{"amount":"80.00","code":"USD"}},
                 {"name":"Hosting","qty":"1","unit_cost":{"amount":"120.00","code":"USD"},"taxName1":"Sales Tax","taxAmount1":"8"}]'
```

**Arguments**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--client` | yes | — | Client name or organization (resolved to a customer id). |
| `--name` | single-line | — | Line-item name/service. Required unless `--lines-json` is used. |
| `--qty` | no | `1` | Quantity for the single line. |
| `--unit-cost` | single-line | — | Unit price. Required unless `--lines-json` is used. |
| `--description` | no | — | Line description. |
| `--tax-name` | no | — | Tax label applied to the single line, e.g. `Sales Tax`. |
| `--tax-rate` | no | `0` | Tax percent for `--tax-name`, e.g. `8` for 8%. |
| `--lines-json` | no | — | JSON array of full line dicts; overrides the single-line flags. |
| `--create-date` | no | today | Invoice date, `YYYY-MM-DD`. |
| `--currency-code` | no | `USD` | ISO currency code. |
| `--send` | no | draft | Mark the invoice as Sent after creating it. |

**Returns**

```json
{
  "id": 308117,
  "invoice_number": "0000004",
  "client": "d1",
  "amount": "324.00",
  "currency": "USD",
  "status": "draft",
  "create_date": "2026-06-07"
}
```

## Notes

- **Writes data** — this creates a real invoice in the account.
- A draft is created by default; pass `--send` to finalize it (no email is sent).
- Line totals are computed by FreshBooks; tax is a percent rate on the line subtotal.
- The account ID is resolved at runtime from the authenticated login
  (see `noui_runtime/freshbooks_account.py`); set `FRESHBOOKS_ACCOUNT_ID` to override.
- If a call returns 401/403, the operation re-sniffs a fresh bearer once and retries.

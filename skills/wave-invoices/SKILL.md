---
name: wave-invoices
description: "List, create, send, and record payments on Wave invoices via Tabby-routed GraphQL. Use when the user wants to see invoices, draft/send an invoice, bill a customer, or mark an invoice paid in Wave. Reads and writes data. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Invoices

List, create, send, and record payments against invoices for the authenticated
Wave business. Each operation under `operations/` is a standalone CLI script
that prints a JSON response to stdout.

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Wave browser session** (see `noui_runtime/execute.py` and
`noui_runtime/wave_gql.py`). GraphQL calls go to
`gql.waveapps.com/graphql/public`. The session's own auth is applied by the
browser, so no Bearer token is sniffed or passed from Python.

Customers, products, and payment accounts are resolved by name via
`noui_runtime/wave_resolve.py`. The business id is resolved via the `businesses`
query; set `WAVE_BUSINESS_ID` to override.

## Prerequisites

1. **Tabby is running with the `wave` profile, authenticated, with the Wave dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
   ```
   Login is human-in-the-loop in the Tabby browser session.
2. **Agent credentials** for Tabby token exchange (`TABBY_CLIENT_ID` / `TABBY_CLIENT_SECRET`).
3. The Tabby session must have a page open on `app.waveapps.com` at call time.

## Operations

### list_invoices — list invoices

```bash
.venv/bin/python operations/list_invoices.py
.venv/bin/python operations/list_invoices.py --customer-id "Q3VzdG9tZXI6..."
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--customer-id` | no | — | Filter to one customer (GraphQL id). |
| `--page` | no | `1` | 1-based page number. |
| `--page-size` | no | `50` | Invoices per page. |

### get_invoice — fetch one invoice

```bash
.venv/bin/python operations/get_invoice.py --invoice-id <id>
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--invoice-id` | yes | — | Wave invoice GraphQL id. |

Returns line items, totals, balance, customer, and payment status.

### create_invoice — create an invoice

```bash
.venv/bin/python operations/create_invoice.py \
  --customer "Acme Co" --description "Consulting" --quantity 2 --unit-price 500 --send
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--customer` | yes | — | Customer name (resolved or created). |
| `--description` | yes | — | Line item description; also used to match/create a sold product. |
| `--quantity` | no | `1` | Line item quantity. |
| `--unit-price` | no | `0` | Unit price. |
| `--date` | no | today | Invoice date (`YYYY-MM-DD`). |
| `--due-date` | no | — | Due date (`YYYY-MM-DD`). |
| `--send` | no | false | Email the invoice after creation (`invoiceSend`). |

Creates a sold product automatically if one matching the description does not exist.

### send_invoice — email an invoice

```bash
.venv/bin/python operations/send_invoice.py --invoice-id <id>
.venv/bin/python operations/send_invoice.py --invoice-id <id> --to "billing@acme.com"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--invoice-id` | yes | — | Wave invoice GraphQL id. |
| `--to` | no | customer email | Comma-separated recipient list. |
| `--subject` | no | — | Email subject override. |
| `--message` | no | — | Email body override. |

Requires `Business.emailSendEnabled` on the Wave account.

### record_payment — mark an invoice paid

```bash
.venv/bin/python operations/record_payment.py --invoice-id <id> --amount 1000 --account "Cash on Hand"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--invoice-id` | yes | — | Wave invoice GraphQL id. |
| `--amount` | yes | — | Payment amount. |
| `--account` | yes | — | Payment account name or id (from `wave-accounting list_accounts`). |
| `--date` | no | today | Payment date (`YYYY-MM-DD`). |
| `--method` | no | `CASH` | Payment method code. |

**Full demo flow:** `create_invoice --send` → `record_payment`.

## Notes

- Write operations (`create_invoice`, `send_invoice`, `record_payment`) modify real data.
- Reference data (business, accounts, products) lives in `wave-accounting`.
- Wave's public GraphQL API does not expose vendor/bill create mutations; expenses
  via `moneyTransactionCreate` require classic accounting and are out of scope here.
- Auth is handled by the Tabby browser session; on failure, refresh with
  `tabby session ensure --profile wave`.

---
name: wave-invoices
description: "List, create, send, and record payments on invoices in Wave. Use when the user wants to see invoices, draft/send an invoice, bill a customer, or mark an invoice paid in Wave. Reads and writes data. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Invoices

List, create, send, and record payments against invoices for the authenticated
Wave business. Each operation under `operations/` is a standalone CLI script
that prints JSON to stdout.

## How it works

Each operation calls `gql.waveapps.com/graphql/public` through Tabby's
`POST /execute/fetch`, which runs `fetch()` **inside the authenticated Wave
browser session** (see `noui_runtime/execute.py`). The session's own auth is
applied by the browser, so no token is extracted or passed from Python.
Customers, products, and payment accounts are resolved by name via
`noui_runtime/wave_resolve.py`. The business id is resolved via the `businesses`
query (see `noui_runtime/wave_gql.py`); override with `WAVE_BUSINESS_ID`.

## Prerequisites

```bash
.venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
```

Login is human-in-the-loop in the Tabby session.

## Operations

### list_invoices / get_invoice

```bash
.venv/bin/python operations/list_invoices.py
.venv/bin/python operations/get_invoice.py --invoice-id <id>
```

### create_invoice

```bash
.venv/bin/python operations/create_invoice.py \
  --customer "Acme Co" --description "Consulting" --quantity 2 --unit-price 500 --send
```

Creates a sold product automatically if one matching the description does not exist.

### send_invoice

```bash
.venv/bin/python operations/send_invoice.py --invoice-id <id>
```

Requires `Business.emailSendEnabled` on the Wave account.

### record_payment

```bash
.venv/bin/python operations/record_payment.py --invoice-id <id> --amount 1000 --account "Cash on Hand"
```

**Full demo flow:** `create_invoice --send` → `record_payment`.

## Notes

- Write operations (`create_invoice`, `send_invoice`, `record_payment`) modify real data.
- Reference data (business, accounts, products) lives in `wave-accounting`.
- Wave's public GraphQL API does not expose vendor/bill create mutations; expenses
  via `moneyTransactionCreate` require classic accounting and are out of scope here.

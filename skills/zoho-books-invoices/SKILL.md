---
name: zoho-books-invoices
description: "List, create, email, and record payments on invoices in Zoho Books. Use when the user wants to see invoices, draft/issue/send an invoice, bill a customer, or mark an invoice paid in Zoho Books. Reads and writes data. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Invoices

List, create, email, and record payments against invoices for the authenticated
Zoho Books organization. Each operation under `operations/` is a standalone CLI
script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated Zoho Books browser session** via
CDP. Calls hit the `books.zoho.in/api/v3/*` REST API with session cookies
(`credentials:'include'`); writes add a sniffed `X-ZCSRF-TOKEN` header. The
`organization_id` is parsed from the open Books tab URL. See
`noui_runtime/zoho_books.py`. Customers and deposit accounts are resolved by
name via `noui_runtime/zoho_resolve.py`.

Region defaults to `books.zoho.in`; override with `ZOHO_BOOKS_DOMAIN` /
`ZOHO_ORGANIZATION_ID`.

## Prerequisites

1. **Tabby running with the `zoho-books` profile, authenticated, with the Books dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile zoho-books --open https://books.zoho.in
   ```
   Zoho uses OTP-only sign-in, so login is human-in-the-loop via `chrome://inspect`
   (`localhost:9222`).

## Operations

### list_invoices

```bash
.venv/bin/python operations/list_invoices.py
.venv/bin/python operations/list_invoices.py --status unpaid
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--status` | no | — | `draft`/`sent`/`overdue`/`paid`/`unpaid`/`all`. |
| `--page` | no | `1` | 1-based page number. |

### get_invoice

```bash
.venv/bin/python operations/get_invoice.py --invoice-id <id>
```

### create_invoice

```bash
.venv/bin/python operations/create_invoice.py \
  --customer "Demo Client Ltd" --description "Consulting services" --quantity 2 --rate 500 --send
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--customer` | yes | — | Customer name or contact_id. |
| `--description` | yes | — | Line item description. |
| `--quantity` | no | `1` | Line item quantity. |
| `--rate` | no | `0` | Line item unit price. |
| `--date` / `--due-date` | no | — | Dates `YYYY-MM-DD`. |
| `--send` | no | draft | Mark the invoice **Sent** after creating. |

### email_invoice

```bash
.venv/bin/python operations/email_invoice.py --invoice-id <id>
.venv/bin/python operations/email_invoice.py --invoice-id <id> --to "billing@client.com"
```

Uses Zoho's default email template (recipient/subject/body) unless overridden.
Emailing a draft marks it Sent.

### record_payment

```bash
.venv/bin/python operations/record_payment.py --invoice-id <id> --amount 1000 --account "Petty Cash"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--invoice-id` | yes | — | Invoice to pay (not a draft). |
| `--amount` | yes | — | Amount applied. |
| `--account` | yes | — | Deposit account name or id (bank/cash). |
| `--date` | no | today | Payment date `YYYY-MM-DD`. |
| `--mode` | no | `cash` | `cash`/`banktransfer`/`check`/`creditcard`/... |
| `--reference` | no | — | Reference number. |

**Full demo flow:** `create_invoice --send` → `email_invoice` → `record_payment`.

## Notes

- `create_invoice`, `email_invoice`, and `record_payment` **write data**.
- Reference data (accounts, taxes, items, organization) lives in `zoho-books-accounting`.
- If a write returns 401/403, the runtime re-sniffs a fresh CSRF token once and retries.

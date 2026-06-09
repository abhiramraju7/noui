---
name: zoho-books-accounting
description: "Read Zoho Books reference data: organization profile, chart of accounts, tax rates, bank/cash accounts, and items (products/services). Read-only. Use when the user wants to inspect accounts, taxes, items, or org settings in Zoho Books, or to look up ids needed for invoices/expenses/payments. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Accounting (reference data)

Read reference data for the authenticated Zoho Books organization. Each
operation under `operations/` is a standalone CLI script that prints a JSON
response to stdout. **Read-only.**

## How it works

Execution runs **inside Tabby's authenticated Zoho Books browser session** via
CDP against `books.zoho.in/api/v3/*` with session cookies
(`credentials:'include'`). The `organization_id` is parsed from the open Books
tab URL. See `noui_runtime/zoho_books.py`.

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

### get_organization

```bash
.venv/bin/python operations/get_organization.py
```

### list_chart_of_accounts

```bash
.venv/bin/python operations/list_chart_of_accounts.py
.venv/bin/python operations/list_chart_of_accounts.py --type expense
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--type` | no | — | Client-side filter on account_type substring (income/expense/bank/...). |

### list_taxes

```bash
.venv/bin/python operations/list_taxes.py
```

### list_bank_accounts

```bash
.venv/bin/python operations/list_bank_accounts.py
```

### list_items

```bash
.venv/bin/python operations/list_items.py
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--page` | no | `1` | 1-based page number. |

## Notes

- All operations are **read-only**.
- Use these to resolve account/tax/item ids for the `zoho-books-invoices` and
  `zoho-books-expenses` write operations.

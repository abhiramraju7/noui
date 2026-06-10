---
name: zoho-books-expenses
description: "List and record expenses in Zoho Books. Use when the user wants to see existing expenses or log/add/record a new expense, bill, or cost (with an expense account and optional vendor) in Zoho Books. Reads and writes data. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Expenses

List and record expenses for the authenticated Zoho Books organization. Each
operation under `operations/` is a standalone CLI script that prints a JSON
response to stdout.

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Zoho Books browser session** (see
`noui_runtime/execute.py` and `noui_runtime/zoho_books.py`). Session cookies and
CSRF are applied by the browser, so nothing is sniffed or passed from Python. The
`organization_id` is resolved via env override, disk cache, or the organizations API.

Region defaults to `books.zoho.in`; override with `ZOHO_BOOKS_DOMAIN` /
`ZOHO_ORGANIZATION_ID`.

## Prerequisites

1. **Tabby running with the `zoho-books` profile, authenticated, with the Books dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile zoho-books --open https://books.zoho.in
   ```
   Zoho uses OTP-only sign-in, so login is human-in-the-loop in the Tabby browser session.

## Operations

### list_expenses

```bash
.venv/bin/python operations/list_expenses.py
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--page` | no | `1` | 1-based page number. |

### create_expense

```bash
.venv/bin/python operations/create_expense.py \
  --account "Transportation Expense" --amount 250 --paid-through "Petty Cash" \
  --description "Taxi to client meeting"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--account` | yes | — | Expense account name or id. |
| `--amount` | yes | — | Expense amount. |
| `--paid-through` | no | `Petty Cash` | Bank/cash account paid from. |
| `--vendor` | no | — | Vendor name or contact_id. |
| `--date` | no | today | Expense date `YYYY-MM-DD`. |
| `--description` | no | — | Note. |
| `--reference` | no | — | Reference number. |

Use `zoho-books-accounting` `list_chart_of_accounts --type expense` and
`list_bank_accounts` to discover valid account names.

## Notes

- `create_expense` **writes data** — it records a real expense in the organization.
- Auth is handled by the Tabby browser session; on a persistent 401/403, refresh it with `tabby session ensure --profile zoho-books`.

---
name: freshbooks-expenses
description: "List and record expenses in FreshBooks. Use when the user wants to see existing expenses or log/add/record a new expense, bill, or cost (with a category and vendor) in FreshBooks. Reads and writes data. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — Expenses

List and record expenses for the authenticated FreshBooks account. Each operation
under `operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP.
The FreshBooks accounting API (`api.freshbooks.com`) authenticates with a short-lived
in-memory **bearer token** (not cookies) and serves wildcard CORS, so each operation
sniffs the live bearer off a real request via CDP `Network` events and replays the call
with `credentials:'omit'`. The token is cached on disk until shortly before its JWT
`exp`. See `noui_runtime/freshbooks_auth.py`.

`create_expense` takes a **category name** (e.g. "Advertising") and resolves it to the
internal category id, and resolves the expense owner (staff id) automatically, so
callers never need internal ids.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop via `chrome://inspect` (`localhost:9222`).
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.

## Operations

### list_expenses — list expenses

```bash
.venv/bin/python operations/list_expenses.py
.venv/bin/python operations/list_expenses.py --per-page 100
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--page` | no | `1` | 1-based page number. |
| `--per-page` | no | `50` | Expenses per page. |

### create_expense — record an expense

```bash
# $120 of advertising from Google Ads, today
.venv/bin/python operations/create_expense.py \
  --amount 120 --category "Advertising" --vendor "Google Ads" --notes "Q2 ad spend"

# Backdated software expense
.venv/bin/python operations/create_expense.py \
  --amount 49.99 --category "Software" --vendor "Adobe" --date 2026-05-01
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--amount` | yes | — | Expense amount. |
| `--category` | yes | — | Category name (resolved to a category id), e.g. `Advertising`. |
| `--vendor` | no | — | Vendor/merchant name. |
| `--date` | no | today | Expense date, `YYYY-MM-DD`. |
| `--currency-code` | no | `USD` | ISO currency code. |
| `--notes` | no | — | Free-text note. |

**Returns**

```json
{
  "id": 1968503,
  "vendor": "Google Ads",
  "amount": "120.00",
  "currency": "USD",
  "category": "Advertising",
  "date": "2026-06-07",
  "notes": "Q2 ad spend"
}
```

## Notes

- `create_expense` **writes data** — it records a real expense in the account.
- Recorded expenses flow into the **expense side of the Profit & Loss report**
  (`freshbooks-reports` skill).
- If the category name isn't found, the error lists example category names.
- The account ID is resolved at runtime from the authenticated login
  (see `noui_runtime/freshbooks_account.py`); set `FRESHBOOKS_ACCOUNT_ID` to override.
- If a call returns 401/403, the operation re-sniffs a fresh bearer once and retries.

---
name: freshbooks-list-invoices
description: "List invoices from a FreshBooks account — invoice number, client, amount, currency, status, and dates. Use when the user wants to see, list, search, or summarize FreshBooks invoices, check outstanding/draft/paid invoices, or report on billing. Read-only. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — List Invoices

Lists invoices for the authenticated FreshBooks account. The single operation under
`operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP —
no credential extraction on the Python side. The FreshBooks accounting API
(`api.freshbooks.com`) authenticates with a short-lived in-memory **bearer token**
(not cookies) and serves wildcard CORS, so the operation sniffs the live bearer off a
real request via CDP `Network` events and replays the call with `credentials:'omit'`.
The token is cached on disk until shortly before its JWT `exp` and re-sniffed on demand.
See `noui_runtime/freshbooks_auth.py`.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open.** Verify / start with:
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop: open Tabby's browser via `chrome://inspect`
   (`localhost:9222`), finish the login + code, and tick "remember this device".
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.

## Operations

### list_invoices — List account invoices

```bash
# All invoices (first page)
.venv/bin/python operations/list_invoices.py

# Filter by display status
.venv/bin/python operations/list_invoices.py --status draft
.venv/bin/python operations/list_invoices.py --status paid

# Paging
.venv/bin/python operations/list_invoices.py --page 2 --per-page 25
```

**Arguments**

| Flag | Default | Description |
|---|---|---|
| `--status` | `""` (all) | Case-insensitive display-status filter: `draft`, `sent`, `paid`, `viewed`, `overdue`, `partial`. |
| `--page` | `1` | 1-based page number. |
| `--per-page` | `15` | Invoices per page. |

**Returns**

```json
{
  "count": 3,
  "page": 1,
  "per_page": 15,
  "total": 3,
  "invoices": [
    {
      "id": 307443,
      "invoice_number": "0000003",
      "client": "d2",
      "amount": "100.00",
      "currency": "USD",
      "status": "draft",
      "create_date": "2026-06-06",
      "due_date": "2026-07-06"
    }
  ]
}
```

## Notes

- Read-only — no invoices are created, sent, or modified.
- The account ID is resolved at runtime from the authenticated login
  (see `noui_runtime/freshbooks_account.py`); set `FRESHBOOKS_ACCOUNT_ID` to override.
- If a call returns 401/403, the operation automatically re-sniffs a fresh bearer once.

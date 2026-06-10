---
name: freshbooks-list-invoices
description: "List invoices from a FreshBooks account — invoice number, client, amount, currency, status, and dates. Use when the user wants to see, list, search, or summarize FreshBooks invoices, check outstanding/draft/paid invoices, or report on billing. Read-only. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — List Invoices

Lists invoices for the authenticated FreshBooks account. The single operation under
`operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated FreshBooks browser session** — no credential extraction
on the Python side. The session's own auth (the SPA's in-page bearer injection on
`api.freshbooks.com`) is applied by the browser, so no token is sniffed or passed
from Python. See `noui_runtime/execute.py` and `noui_runtime/freshbooks_api.py`.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open.** Verify / start with:
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop in the Tabby browser session: finish the login
   + code and tick "remember this device".
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
- Auth is handled by the Tabby browser session; on a persistent 401/403, refresh it with `tabby session ensure --profile freshbooks`.

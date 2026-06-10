---
name: xero-contacts
description: "List and create contacts in Xero. Use when the user wants to see/search existing contacts or add a new customer/supplier contact in Xero. Reads and writes data. Requires an authenticated Tabby session for the `xero` profile."
---

# Xero — Contacts

List and create contacts for the authenticated Xero organisation. Each operation
under `operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Xero browser session** (see `noui_runtime/execute.py`
and `noui_runtime/xero_api.py`). The session's own auth is applied by the browser,
so no bearer token is sniffed or passed from Python. Tenant routing headers are
resolved via `noui_runtime/xero_account.py` (Organisation API or env overrides).

## Prerequisites

1. **Tabby is running with the `xero` profile, authenticated, with `go.xero.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile xero --open https://go.xero.com
   ```
   Xero may require human-in-the-loop login on new devices in the Tabby browser session.
2. The Tabby session must have a page open on `go.xero.com/app/<shortcode>/...` at call time.

## Operations

### list_contacts — list / search contacts

```bash
# All contacts
.venv/bin/python operations/list_contacts.py

# Filter by name/email
.venv/bin/python operations/list_contacts.py --query "demo"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--query` | no | — | Case-insensitive filter on name/email. |
| `--page` | no | `1` | 1-based page number. |

### create_contact — create a contact

```bash
# Customer contact
.venv/bin/python operations/create_contact.py \
  --name "Acme Pty Ltd" --email "billing@acme.com"

# Supplier only
.venv/bin/python operations/create_contact.py \
  --name "Office Supplies Co" --supplier --no-customer
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--name` | yes | — | Contact or company name. |
| `--email` | no | — | Contact email. |
| `--customer` / `--no-customer` | no | customer | Mark as a customer. |
| `--supplier` | no | false | Mark as a supplier. |

**Returns**

```json
{
  "id": "e1e947fa-ce42-46b5-b9f2-83ab4d817247",
  "name": "Acme Pty Ltd",
  "email": "billing@acme.com",
  "status": "ACTIVE",
  "is_customer": true,
  "is_supplier": false
}
```

## Notes

- `create_contact` **writes data** — it adds a real contact to the organisation.
- For Sales/Invoicing page data (invoice list, customers, tax rates, accounts) use
  the separate `xero-invoices` skill (`go.xero.com/api/invoicing/*` BFF).
- **Expenses and Reports** are not available on this org's plan (Expenses page is upsell).
- Override tenant resolution with `XERO_TENANT_ID` and `XERO_TENANT_SHORTCODE` if needed.
- Auth is handled by the Tabby browser session; on a persistent 401/403, refresh it with `tabby session ensure --profile xero`.

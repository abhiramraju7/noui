---
name: zoho-books-contacts
description: "List and create contacts (customers/vendors) in Zoho Books. Use when the user wants to see/search existing contacts or add a new customer or vendor in Zoho Books. Reads and writes data. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Contacts

List and create contacts for the authenticated Zoho Books organization. Each
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
2. The Tabby session must have a page open on `books.zoho.in/app/<org>/...` at call time.

## Operations

### list_contacts

```bash
.venv/bin/python operations/list_contacts.py
.venv/bin/python operations/list_contacts.py --query "demo" --type customer
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--query` | no | — | Case-insensitive filter on name/company/email. |
| `--type` | no | — | `customer` or `vendor`. |
| `--page` | no | `1` | 1-based page number. |

### create_contact

```bash
.venv/bin/python operations/create_contact.py --name "Acme Pvt Ltd" --email "billing@acme.com"
.venv/bin/python operations/create_contact.py --name "Office Supplies Co" --type vendor
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--name` | yes | — | Contact display name. |
| `--email` | no | — | Primary contact email. |
| `--company` | no | `--name` | Company name. |
| `--type` | no | `customer` | `customer` or `vendor`. |
| `--phone` | no | — | Phone number. |

## Notes

- `create_contact` **writes data** — it adds a real contact to the organization.
- For invoices use `zoho-books-invoices`; for reference data (accounts, taxes,
  items, organization) use `zoho-books-accounting`.
- Auth is handled by the Tabby browser session; on a persistent 401/403, refresh it with `tabby session ensure --profile zoho-books`.

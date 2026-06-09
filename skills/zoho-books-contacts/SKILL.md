---
name: zoho-books-contacts
description: "List and create contacts (customers/vendors) in Zoho Books. Use when the user wants to see/search existing contacts or add a new customer or vendor in Zoho Books. Reads and writes data. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Contacts

List and create contacts for the authenticated Zoho Books organization. Each
operation under `operations/` is a standalone CLI script that prints a JSON
response to stdout.

## How it works

Execution runs **inside Tabby's authenticated Zoho Books browser session** via
CDP. The Zoho Books web app (`books.zoho.in`) authenticates with **session
cookies** and guards writes with an `X-ZCSRF-TOKEN` header. Each operation runs
`fetch()` inside the browser with `credentials:'include'` (cookies attached) and
sniffs the CSRF token from a live request for write calls. The
`organization_id` is parsed from the `books.zoho.in/app/<org>#/...` page URL.
See `noui_runtime/zoho_books.py`.

Region defaults to the India DC (`books.zoho.in`). Override with
`ZOHO_BOOKS_DOMAIN` (e.g. `books.zoho.com`) and `ZOHO_ORGANIZATION_ID` if needed.

## Prerequisites

1. **Tabby running with the `zoho-books` profile, authenticated, with the Books dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile zoho-books --open https://books.zoho.in
   ```
   Zoho uses OTP-only sign-in, so login is human-in-the-loop via `chrome://inspect`
   (`localhost:9222`).
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
- If a write returns 401/403, the runtime re-sniffs a fresh CSRF token once and retries.

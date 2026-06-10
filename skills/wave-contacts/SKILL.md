---
name: wave-contacts
description: "List and create customers in Wave. Use when the user wants to see/search existing customers or add a new customer in Wave. Reads and writes data. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Customers

List and create customers for the authenticated Wave business. Each operation
under `operations/` is a standalone CLI script that prints JSON to stdout.

## How it works

Each operation calls `gql.waveapps.com/graphql/public` through Tabby's
`POST /execute/fetch` endpoint, which runs `fetch()` **inside the authenticated
Wave browser session** (see `noui_runtime/execute.py`). The session's own auth is
applied by the browser, so no token is extracted or passed from Python. The
business id is resolved from the first business returned by the `businesses`
query (see `noui_runtime/wave_gql.py`). Override with `WAVE_BUSINESS_ID`.

## Prerequisites

1. **Tabby running with the `wave` profile, authenticated, with the Wave dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
   ```
   Login is human-in-the-loop in the Tabby session.

## Operations

### list_customers

```bash
.venv/bin/python operations/list_customers.py
.venv/bin/python operations/list_customers.py --query "acme"
```

### create_customer

```bash
.venv/bin/python operations/create_customer.py --name "Acme Co" --email "billing@acme.com"
```

## Notes

- `create_customer` **writes data**.
- For invoices use `wave-invoices`; for accounts/products use `wave-accounting`.
- Auth is handled by the Tabby browser session; if a call fails with 401/403, refresh the session with `tabby session ensure --profile wave`.

---
name: wave-contacts
description: "List and create customers in Wave via Tabby-routed GraphQL. Use when the user wants to see/search existing customers or add a new customer in Wave. Reads and writes data. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Customers

List and create customers for the authenticated Wave business. Each operation
under `operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Wave browser session** (see `noui_runtime/execute.py` and
`noui_runtime/wave_gql.py`). GraphQL calls go to
`gql.waveapps.com/graphql/public`. The session's own auth — cookies plus the SPA's
in-page fetch wrapper — is applied by the browser, so no Bearer token is sniffed or
passed from Python.

The business id is resolved from the first business returned by the `businesses`
query; set `WAVE_BUSINESS_ID` to override.

## Prerequisites

1. **Tabby is running with the `wave` profile, authenticated, with the Wave dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
   ```
   Login is human-in-the-loop in the Tabby browser session.
2. **Agent credentials** for Tabby token exchange (`TABBY_CLIENT_ID` / `TABBY_CLIENT_SECRET` in `.env` or the environment).
3. The Tabby session must have a page open on `app.waveapps.com` at call time.

## Operations

### list_customers — list / search customers

```bash
# All customers
.venv/bin/python operations/list_customers.py

# Filter by name or email
.venv/bin/python operations/list_customers.py --query "acme"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--query` | no | — | Case-insensitive filter on name/email. |
| `--page` | no | `1` | 1-based page number. |
| `--page-size` | no | `50` | Customers per page. |

**Returns**

```json
{
  "count": 1,
  "page": 1,
  "customers": [
    {
      "id": "Q3VzdG9tZXI6...",
      "name": "Acme Co",
      "email": "billing@acme.com",
      "phone": null,
      "outstanding": "0.00"
    }
  ]
}
```

### create_customer — create a customer

```bash
.venv/bin/python operations/create_customer.py --name "Acme Co" --email "billing@acme.com"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--name` | yes | — | Customer display name. |
| `--email` | no | — | Contact email. |
| `--phone` | no | — | Contact phone. |

**Returns**

```json
{
  "id": "Q3VzdG9tZXI6...",
  "name": "Acme Co",
  "email": "billing@acme.com",
  "phone": null
}
```

## Notes

- `create_customer` **writes data** — it adds a real customer to the business.
- New customers become valid `--customer` targets for `wave-invoices create_invoice`.
- For invoices use `wave-invoices`; for accounts/products use `wave-accounting`.
- Auth is handled by the Tabby browser session; on a persistent 401/403 or
  `No healthy Tabby session`, refresh with `tabby session ensure --profile wave`.

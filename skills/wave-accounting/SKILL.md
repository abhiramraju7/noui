---
name: wave-accounting
description: "Read Wave reference data: business profile, chart of accounts, and products/services. Read-only. Use when the user wants to inspect accounts or products in Wave, or to look up ids needed for invoices. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Accounting (reference data)

Read reference data for the authenticated Wave business. **Read-only.**

## How it works

GraphQL calls to `gql.waveapps.com/graphql/public` run through Tabby's
`POST /execute/fetch`, i.e. `fetch()` executed **inside the authenticated Wave
browser session** — no token is extracted or passed from Python. See
`noui_runtime/execute.py` and `noui_runtime/wave_gql.py`.

## Prerequisites

```bash
.venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
```

## Operations

### get_business

```bash
.venv/bin/python operations/get_business.py
```

### list_accounts

```bash
.venv/bin/python operations/list_accounts.py
.venv/bin/python operations/list_accounts.py --type ASSET
```

### list_products

```bash
.venv/bin/python operations/list_products.py
```

## Notes

- All operations are **read-only**.
- Use these to discover payment account names for `wave-invoices record_payment`.

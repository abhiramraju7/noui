---
name: wave-accounting
description: "Read Wave reference data via Tabby-routed GraphQL: business profile, chart of accounts, and products/services. Read-only. Use when the user wants to inspect accounts or products in Wave, or to look up ids needed for invoices. Requires an authenticated Tabby session for the `wave` profile."
---

# Wave — Accounting (reference data)

Read reference data for the authenticated Wave business. **Read-only.**

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Wave browser session** (see `noui_runtime/execute.py` and
`noui_runtime/wave_gql.py`). GraphQL calls go to
`gql.waveapps.com/graphql/public`. The session's own auth is applied by the
browser, so no Bearer token is sniffed or passed from Python.

The business id is resolved via the `businesses` query; set `WAVE_BUSINESS_ID`
to override.

## Prerequisites

1. **Tabby is running with the `wave` profile, authenticated, with the Wave dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile wave --open https://app.waveapps.com
   ```
2. **Agent credentials** for Tabby token exchange (`TABBY_CLIENT_ID` / `TABBY_CLIENT_SECRET`).
3. The Tabby session must have a page open on `app.waveapps.com` at call time.

## Operations

### get_business — business profile

```bash
.venv/bin/python operations/get_business.py
```

Returns id, name, currency, location, and accounting mode flags
(`is_classic_accounting`, `is_personal`).

### list_accounts — chart of accounts

```bash
.venv/bin/python operations/list_accounts.py
.venv/bin/python operations/list_accounts.py --type ASSET
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--type` | no | — | Filter by account type (`INCOME`, `EXPENSE`, `ASSET`, `LIABILITY`, `EQUITY`). |
| `--page` | no | `1` | 1-based page number. |
| `--page-size` | no | `100` | Accounts per page. |

Use account **names** from this list as `--account` values in
`wave-invoices record_payment`.

### list_products — products and services

```bash
.venv/bin/python operations/list_products.py
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--page` | no | `1` | 1-based page number. |
| `--page-size` | no | `50` | Products per page. |

Returns id, name, unit price, and sold/bought flags.

## Notes

- All operations are **read-only**.
- Use these to discover payment account names for `wave-invoices record_payment`
  and product names for invoice line items.
- Auth is handled by the Tabby browser session; on failure, refresh with
  `tabby session ensure --profile wave`.

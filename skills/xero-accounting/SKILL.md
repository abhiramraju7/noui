---
name: xero-accounting
description: "Read Xero accounting reference data via the public accounting API (api.xro/2.0): organisation profile, chart of accounts, tax rates, branding themes, and purchase orders. Read-only. Requires an authenticated Tabby session for the `xero` profile."
---

# Xero — Accounting

Read-only access to Xero accounting reference data through the public accounting
API (`api.xero.com/api.xro/2.0`). Each operation under `operations/` is a
standalone CLI script that prints JSON to stdout.

## How it works

Execution runs inside Tabby's authenticated Xero browser via CDP. The Xero SPA
holds a short-lived in-memory **bearer token** and calls `api.xero.com` with
`xero-tenant-id`, `xero-tenant-shortcode`, and `xero-shell-app-name` headers. Each
operation sniffs the live bearer, resolves the tenant, and replays the call with
`credentials:'omit'`. See `noui_runtime/xero_api.py`, `xero_auth.py`, `xero_account.py`.

## Prerequisites

1. **Tabby running with the `xero` profile, authenticated, with `go.xero.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile xero --open https://go.xero.com
   ```
2. The browser must be on `go.xero.com/app/<shortcode>/...` at call time.

## Operations

| Operation | API path |
|---|---|
| `get_organisation` | `GET /api.xro/2.0/Organisation` |
| `list_accounts` | `GET /api.xro/2.0/Accounts` |
| `list_tax_rates` | `GET /api.xro/2.0/TaxRates` |
| `list_branding_themes` | `GET /api.xro/2.0/BrandingThemes` |
| `list_purchase_orders` | `GET /api.xro/2.0/PurchaseOrders` |

### get_organisation

```bash
.venv/bin/python operations/get_organisation.py
```

### list_accounts

```bash
.venv/bin/python operations/list_accounts.py
.venv/bin/python operations/list_accounts.py --type REVENUE
```

### list_tax_rates

```bash
.venv/bin/python operations/list_tax_rates.py
```

### list_branding_themes

```bash
.venv/bin/python operations/list_branding_themes.py
```

### list_purchase_orders

```bash
.venv/bin/python operations/list_purchase_orders.py
```

## Notes

- **Read-only.** No writes in this skill.
- On this org the bearer is scoped so **Invoices, Reports, Payments, Items, Quotes,
  and CreditNotes return 403** on `api.xro/2.0`. Use the `xero-invoices` skill
  (`go.xero.com/api/invoicing/*` BFF) for invoice list/create instead.
- For contacts use `xero-contacts`; for invoice Sales-page data use `xero-invoices`.
- Override tenant with `XERO_TENANT_ID` / `XERO_TENANT_SHORTCODE` if needed.

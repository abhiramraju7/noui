---
name: xero-invoices
description: "List and create invoices in Xero using the same BFF URLs the Sales/Invoicing UI calls (invoice/find, invoice/create, customer/find, appData, taxRateAce, account). Requires an authenticated Tabby session for the `xero` profile."
---

# Xero — Sales Invoices

Access to the Xero **Sales > Invoices** page APIs (read + create draft). Each operation
under `operations/` is a standalone CLI script that prints JSON to stdout.

These operations call **`go.xero.com/api/invoicing/*`** — the same BFF endpoints
the Sales/Invoicing SPA uses — not `api.xero.com/api.xro/2.0/Invoices` (which
returns 403 outside the UI context).

## How it works

Execution runs through Tabby's `POST /execute/fetch`, which runs `fetch()`
**inside the authenticated Xero browser session** (see `noui_runtime/execute.py`
and `noui_runtime/xero_invoicing.py`). The session's own auth is applied by the
browser, so no bearer token or header bundle is sniffed from Python. Tenant routing
headers come from `noui_runtime/xero_account.py`.

## Prerequisites

1. **Tabby running with the `xero` profile, authenticated, with `go.xero.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile xero --open https://go.xero.com
   ```
2. The browser must be on `go.xero.com/app/<shortcode>/...` at call time.

## Xero has two invoice UIs

| UI | Page URL | List API |
|---|---|---|
| **New SPA** (use this) | `go.xero.com/app/<shortcode>/invoicing/list` | `GET /api/invoicing/invoice/find` |
| **New invoice form** | `go.xero.com/app/<shortcode>/invoicing/?optInAndDefaultToNew=true` | `GET /api/invoicing/invoice/latest` |
| **Legacy** (ignore) | `go.xero.com/AccountsReceivable/Search.aspx` | old ASP.NET — no `/api/invoicing/*` BFF |

The create URL loads a different set of calls than the list page — notably
`invoice/latest` and `invoice/latest/status/DRAFT` instead of `invoice/find`.
An empty org returns `[]` from `invoice/latest` (200) but 404 `"object is NULL"`
from `invoice/find` (both mean no invoices yet).

## Operations

All paths mirror what the new Sales SPA loads:

| Operation | BFF path (as used by UI) |
|---|---|
| `list_invoices` | `GET /api/invoicing/invoice/find` |
| `list_invoice_customers` | `GET /api/invoicing/customer/find` |
| `get_invoice_settings` | `GET /api/invoicing/appData` |
| `list_tax_rates` | `GET /api/invoicing/taxRateAce` |
| `list_sales_accounts` | `GET /api/invoicing/account` |
| `create_invoice` | `POST /api/invoicing/invoice/create` |
| `send_invoice` | `POST /api/invoicing/invoice/email` |
| `mark_payment` | `PUT /api.xro/2.0/payments` |

### list_invoices

```bash
.venv/bin/python operations/list_invoices.py
.venv/bin/python operations/list_invoices.py --status DRAFT
```

| Flag | Default | Description |
|---|---|---|
| `--status` | `ALL` | Status tab: ALL, DRAFT, AWAITING PAYMENT, PAID, etc. |
| `--page` | `1` | 1-based page number. |

Returns `{count, page, status, invoices: [...]}`. An empty org returns `count: 0`
(the UI endpoint returns 404 `"object is NULL"` which is normalised to an empty list).

### list_invoice_customers

```bash
.venv/bin/python operations/list_invoice_customers.py
.venv/bin/python operations/list_invoice_customers.py --query "demo"
```

### get_invoice_settings

```bash
.venv/bin/python operations/get_invoice_settings.py
```

Returns base currency, country, default tax basis, and auto-tax status.

### list_tax_rates

```bash
.venv/bin/python operations/list_tax_rates.py
```

### list_sales_accounts

```bash
.venv/bin/python operations/list_sales_accounts.py
```

### create_invoice

```bash
.venv/bin/python operations/create_invoice.py \
  --customer "Demo Client Ltd" \
  --description "Consulting" \
  --unit-price 1000
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--customer` | yes | — | Customer name (resolved via customer/find). |
| `--description` | yes | — | Line item description. |
| `--quantity` | no | `1` | Line item quantity. |
| `--unit-price` | no | `0` | Line item unit price. |
| `--account-code` | no | `200` | Sales account code. |
| `--approve` | no | draft | Create as **AUTHORISED** (approved) instead of draft. |

Creates an invoice via `POST /api/invoicing/invoice/create` (from workflow capture `b76f8563`).
With `--approve` it is created as AUTHORISED so it can be emailed and paid.

### send_invoice

Email an **approved** invoice to its customer (from workflow capture `4e56869b`).

```bash
.venv/bin/python operations/send_invoice.py --invoice-id <id>
.venv/bin/python operations/send_invoice.py --invoice-id <id> \
  --to "billing@client.com" --subject "Your invoice" --message "Thanks for your business"
```

| Flag | Required | Description |
|---|---|---|
| `--invoice-id` | yes | Invoice id (from create_invoice / list_invoices). |
| `--to` | no | Recipient override (defaults to the customer email). |
| `--subject` / `--message` | no | Override the org's default email template. |
| `--no-pdf` | no | Do not attach the PDF. |
| `--copy-me` | no | Send the org a copy. |

### mark_payment

Record a payment against an invoice (from workflow capture `fd1c0ad4`).

```bash
.venv/bin/python operations/mark_payment.py --invoice-id <id> \
  --amount 1000 --account "Owner A Drawings"
```

| Flag | Required | Description |
|---|---|---|
| `--invoice-id` | yes | Invoice id (must be AUTHORISED). |
| `--amount` | yes | Payment amount. |
| `--account` | yes | Deposit account id, code, or name (resolved via account/payable). |
| `--date` | no | Payment date YYYY-MM-DD (default today). |
| `--reference` | no | Optional payment reference. |

**Full demo flow:** `create_invoice --approve` → `send_invoice` → `mark_payment`.

## Notes
- **Expenses and Reports** are not included — this org's Expenses page is an upsell
  and those APIs are not available on the current plan.
- For full contact CRUD use the separate `xero-contacts` skill (`api.xro/2.0/Contacts`).
- Override tenant with `XERO_TENANT_ID` / `XERO_TENANT_SHORTCODE` if needed.

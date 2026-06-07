---
name: freshbooks-reports
description: "Pull FreshBooks accounting reports: Profit & Loss (income, expenses, gross margin, net profit), Sales Tax Summary (tax collected per tax name, total invoiced, total tax), and Accounts Receivable aging (per-client outstanding balances by age bucket) for a date range. Use when the user wants a P&L, profit and loss statement, income/expense summary, sales tax report, tax collected/liability summary, A/R aging, outstanding/overdue receivables, or financial report from FreshBooks. Read-only. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — Reports

FreshBooks accounting reports for the authenticated business. Each operation under
`operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP.
The FreshBooks accounting API (`api.freshbooks.com`) authenticates with a short-lived
in-memory **bearer token** (not cookies) and serves wildcard CORS, so each operation
sniffs the live bearer off a real request via CDP `Network` events and replays the call
with `credentials:'omit'`. The token is cached on disk until shortly before its JWT
`exp`. See `noui_runtime/freshbooks_auth.py`.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop via `chrome://inspect` (`localhost:9222`).
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.

## Operations

### get_profit_and_loss — Profit & Loss report

```bash
# Full-year P&L (accrual basis)
.venv/bin/python operations/get_profit_and_loss.py --start-date 2026-01-01 --end-date 2026-12-31

# Quarter, cash basis, in a specific currency
.venv/bin/python operations/get_profit_and_loss.py \
  --start-date 2026-01-01 --end-date 2026-03-31 --currency-code USD --cash-based
```

**Arguments**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--start-date` | yes | — | Period start, `YYYY-MM-DD`. |
| `--end-date` | yes | — | Period end, `YYYY-MM-DD`. |
| `--currency-code` | no | `USD` | ISO currency code. |
| `--cash-based` | no | accrual | Use cash-basis accounting instead of accrual. |

**Returns**

```json
{
  "company_name": "Abhiram's Company",
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "currency_code": "USD",
  "cash_based": false,
  "total_income":   {"description": "Gross Profit",   "amount": "0.00", "currency": "USD"},
  "total_expenses": {"description": "Total Expenses",  "amount": "0.00", "currency": "USD"},
  "net_profit":     {"description": "Net Profit (USD)","amount": "0.00", "currency": "USD"},
  "gross_margin":   {"description": "Gross Margin",    "amount": "0.00", "currency": "%"},
  "income":   [{"description": "Sales", "amount": "0.00", "currency": "USD"}],
  "expenses": [{"description": "Expenses", "amount": "0.00", "currency": "USD"}]
}
```

### get_sales_tax_summary — Sales Tax Summary report

```bash
# Full-year sales tax summary (accrual basis)
.venv/bin/python operations/get_sales_tax_summary.py --start-date 2026-01-01 --end-date 2026-12-31

# Quarter, cash basis
.venv/bin/python operations/get_sales_tax_summary.py \
  --start-date 2026-01-01 --end-date 2026-03-31 --cash-based
```

**Arguments**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--start-date` | yes | — | Period start, `YYYY-MM-DD`. |
| `--end-date` | yes | — | Period end, `YYYY-MM-DD`. |
| `--currency-code` | no | `USD` | ISO currency code. |
| `--cash-based` | no | accrual | Use cash-basis accounting instead of accrual. |

**Returns**

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "currency_code": "USD",
  "cash_based": false,
  "total_invoiced":       {"amount": "695.00", "currency": "USD"},
  "total_tax_collected":  {"amount": "45.00",  "currency": "USD"},
  "taxes": [
    {
      "tax_name": "Sales Tax",
      "tax_collected":            {"amount": "40.00",  "currency": "USD"},
      "tax_paid":                 {"amount": "0.00",   "currency": "USD"},
      "net_tax":                  {"amount": "40.00",  "currency": "USD"},
      "taxable_amount_collected": {"amount": "500.00", "currency": "USD"},
      "net_taxable_amount":       {"amount": "500.00", "currency": "USD"}
    }
  ]
}
```

### get_accounts_receivable_aging — A/R aging report

```bash
# Outstanding receivables aged into 0-30 / 31-60 / 61-90 / 91+ buckets
.venv/bin/python operations/get_accounts_receivable_aging.py \
  --start-date 2026-01-01 --end-date 2026-12-31
```

**Arguments**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--start-date` | yes | — | Period start, `YYYY-MM-DD`. |
| `--end-date` | yes | — | Period end, `YYYY-MM-DD`. |
| `--currency-code` | no | `USD` | ISO currency code. |

**Returns**

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "currency_code": "USD",
  "total_outstanding": "1135.00",
  "buckets": {"0-30": "0.00", "31-60": "0.00", "61-90": "0.00", "91+": "1135.00"},
  "clients": [
    {"client": "Amazon", "email": "", "0-30": "0.00", "31-60": "0.00",
     "61-90": "0.00", "91+": "595.00", "total": "595.00"}
  ]
}
```

## Notes

- Read-only — no data is modified.
- The account ID and business UUID are resolved at runtime from the authenticated
  login (see `noui_runtime/freshbooks_account.py`); set `FRESHBOOKS_ACCOUNT_ID` /
  `FRESHBOOKS_BUSINESS_UUID` to override.
- Sales tax only appears once invoices are **finalized (Sent)** and carry tax lines; pure drafts contribute nothing.
- A/R aging reflects **outstanding** invoice balances, so recording payments
  (`freshbooks-mark-payment` skill) reduces the relevant client's bucket.
- On a trial/empty account the figures are `0.00`; against a real account they reflect actual ledger data.
- If a call returns 401/403, the operation re-sniffs a fresh bearer once and retries.

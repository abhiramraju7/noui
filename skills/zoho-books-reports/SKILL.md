---
name: zoho-books-reports
description: "Pull Zoho Books financial reports: Profit & Loss (income, COGS, gross/operating profit, expenses) and Balance Sheet (assets, liabilities, equity) for a date range. Read-only. Use when the user wants a P&L, income/expense summary, balance sheet, or financial report from Zoho Books. Requires an authenticated Tabby session for the `zoho-books` profile."
---

# Zoho Books — Reports

Pull financial reports for the authenticated Zoho Books organization. Each
operation under `operations/` is a standalone CLI script that prints a JSON
response to stdout. **Read-only.**

## How it works

Execution runs **inside Tabby's authenticated Zoho Books browser session** via
CDP against `books.zoho.in/api/v3/reports/*` with session cookies. The nested
report sections are flattened into `rows` of `{name, total, depth}`. The
`organization_id` is parsed from the open Books tab URL. See
`noui_runtime/zoho_books.py`.

Region defaults to `books.zoho.in`; override with `ZOHO_BOOKS_DOMAIN` /
`ZOHO_ORGANIZATION_ID`.

## Prerequisites

1. **Tabby running with the `zoho-books` profile, authenticated, with the Books dashboard open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile zoho-books --open https://books.zoho.in
   ```
   Zoho uses OTP-only sign-in, so login is human-in-the-loop via `chrome://inspect`
   (`localhost:9222`).

## Operations

### profit_and_loss

```bash
.venv/bin/python operations/profit_and_loss.py --from-date 2026-04-01 --to-date 2026-06-30
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--from-date` | yes | — | Start date `YYYY-MM-DD`. |
| `--to-date` | no | today | End date `YYYY-MM-DD`. |

### balance_sheet

```bash
.venv/bin/python operations/balance_sheet.py --to-date 2026-06-30
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--to-date` | no | today | As-of date `YYYY-MM-DD`. |
| `--from-date` | no | — | Optional period start `YYYY-MM-DD`. |

## Notes

- All operations are **read-only**.
- The P&L requires a `from_date`; the Balance Sheet is point-in-time as of `to_date`.

---
name: xero-accounting
description: NoUI workflows for Xero — full double-entry accounting. Use when the user's platform is Xero, for contacts, invoices, bills, accounts, items, payments, tax rates, and reconciliation support.
---

# Xero Accounting

Xero is a full double-entry accounting platform for SMBs. API resources are scoped to a tenant/organisation resolved from the authenticated connection at runtime.

Use together with the shared `accounting-tax-analyst` skill for role, output formats, and safety rules.

## Supported NoUI operations

### Read (perform when needed)

| Operation | Notes |
|---|---|
| Get organisation | Base currency, financial year end, tax basis |
| List/get contacts | Unified customers **and** suppliers (flags distinguish them) |
| List/get invoices | `ACCREC` (sales invoices) and `ACCPAY` (bills); status: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED |
| List accounts | Chart of accounts with types, codes, and tax defaults |
| List items | Products/services with sales/purchase details |
| List payments | Payments linked to invoices/bills and bank accounts |
| List tax rates | Named tax rates with components — read-only for tax summaries |
| Reports | Where exposed: aged receivables/payables, trial balance, P&L |

### Write (explicit user intent required)

| Operation | Confirmation required |
|---|---|
| Create contact | Show details, confirm first |
| Create invoice | Create as DRAFT; show contact, lines, account codes, tax types; confirm first |
| Authorise/send invoice | Restate number, contact, total; explicit "yes" — authorising posts to the ledger |
| Record payment | Restate invoice, amount, date, bank account; explicit "yes" |

Voiding invoices, deleting contacts, creating/modifying tax rates, and posting manual journals are **not supported** by this skill by default. Modifying tax settings needs explicit confirmation and is better done in the Xero UI.

## Safety requirements

- Resolve tenant ID from the authenticated connection at runtime; never hardcode tenant, account, or contact IDs.
- Line items reference account codes and tax types — use only codes observed in the chart of accounts and tax rate list; never guess.
- Distinguish ACCREC from ACCPAY in every summary; conflating sales and bills corrupts the analysis.
- AUTHORISED invoices affect the ledger; prefer DRAFT and let the user authorise deliberately.

## Common workflows

- **Receivables/payables review**: list ACCREC + ACCPAY by status → overdue by contact → standard summary.
- **Reconciliation support**: list payments ↔ invoices; flag payments without invoice links, partially allocated payments, and invoices AUTHORISED-but-unpaid past due date; cross-check against aged receivables report where available.
- **Tax summary**: list tax rates in use → group invoice lines by tax type → flag lines with missing/exempt tax where unexpected → mandatory disclaimer.

## Edge cases

- Contacts can be both customer and supplier — don't double count.
- Credit notes and prepayments/overpayments affect amount due; report them explicitly if observed.
- Multi-currency invoices carry exchange rates; totals in reports are base currency.
- Status VOIDED/DELETED invoices may appear in listings depending on filters — exclude from open totals and say so.

## Output

Follow the shared skill's output format. Identify records as `Invoice <InvoiceNumber> (Xero ID <InvoiceID>)` using observed values.

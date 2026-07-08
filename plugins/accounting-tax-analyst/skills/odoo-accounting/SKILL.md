---
name: odoo-accounting
description: NoUI workflows for Odoo accounting — partners, customer invoices, vendor bills, products, chart of accounts, payments, journal entries, and taxes. Use when the user's platform is Odoo (any accounting-enabled deployment).
---

# Odoo Accounting

Odoo is a modular open-source ERP; its accounting app provides full double-entry bookkeeping. Deployments vary widely (Community vs. Enterprise, versions, installed modules), so verify what's available rather than assuming. Records are typically accessed via the ORM models below; access is scoped to the authenticated user's company/database at runtime.

Use together with the shared `accounting-tax-analyst` skill for role, output formats, and safety rules.

## Supported NoUI operations

### Read (perform when needed)

| Model / operation | Notes |
|---|---|
| `res.partner` | Customers and vendors (partners); `customer_rank`/`supplier_rank` distinguish roles |
| `account.move` — customer invoices | `move_type=out_invoice` (and `out_refund` for credit notes); state: draft, posted, cancel; payment_state: not_paid, in_payment, paid, partial, reversed |
| `account.move` — vendor bills | `move_type=in_invoice` / `in_refund` |
| `account.move` — journal entries | `move_type=entry`; read-only for reconciliation support |
| `product.product` / `product.template` | Products/services with income/expense accounts |
| `account.account` | Chart of accounts |
| `account.payment` | Payments and their reconciliation state |
| `account.tax` | Tax definitions — read-only for tax summaries |
| Reports | Where exposed: aged partner balances, P&L, tax reports (Enterprise features vary) |

### Write (explicit user intent required)

| Operation | Confirmation required |
|---|---|
| Create partner | Show details, confirm first |
| Create customer invoice | Create in **draft**; show partner, lines, taxes, journal; confirm first |
| Post invoice | Posting writes to the ledger — restate details; explicit "yes" |
| Send invoice (email) | Restate number, recipient, amount; explicit "yes" |
| Register payment | Restate invoice, amount, date, journal; explicit "yes" |

**Not supported by default**: deleting records, cancelling/resetting posted moves, creating/modifying taxes or accounts, posting manual journal entries, and any `unlink` operation. These are high-impact ledger operations — direct the user to the Odoo UI.

## Safety requirements

- Never hardcode database names, company IDs, partner IDs, journal IDs, or account IDs — resolve from the authenticated session and observed data.
- Draft vs. posted is the critical boundary: **posting is a ledger write** and needs its own explicit confirmation, separate from creating the draft.
- Line items reference accounts, taxes, and journals — use only IDs observed in this session; Odoo's defaults (from product/partner/journal config) are preferable to manual guesses, so omit optional fields and let Odoo default them.
- Multi-company databases: confirm which company is in scope before summarizing; totals across companies are usually wrong.
- Report Odoo's computed `amount_total`, `amount_residual`, and `payment_state` rather than recalculating.

## Common workflows

- **Books review**: read out_invoices + in_invoices by state/payment_state → overdue by partner (compare `invoice_date_due` to today) → standard summary.
- **Reconciliation support**: payments with unreconciled lines, invoices `partial` or `in_payment` for extended periods, draft moves older than N days, journal entries without references.
- **Tax summary**: list `account.tax` in use → group invoice lines by tax → flag untaxed lines where taxes are expected → mandatory disclaimer.
- **Vendor/customer review**: partners by rank → duplicates by name/email/VAT → missing VAT/contact fields.

## Edge cases

- Credit notes (`out_refund`/`in_refund`) offset invoices; include them or receivables will be overstated.
- `payment_state=in_payment` means payment registered but not bank-reconciled — distinct from paid; report the distinction.
- Installed localization modules change tax and report structures; describe what's observed, don't assume a locale.
- Version differences (e.g., field renames across Odoo versions): if a field/model isn't available, report the limitation instead of substituting guessed data.

## Output

Follow the shared skill's output format. Identify records as `Invoice <name> (Odoo ID <id>)` using observed values.

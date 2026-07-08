---
name: freshbooks-accounting
description: NoUI workflows for FreshBooks — invoicing and accounting for service businesses. Use when the user's platform is FreshBooks, for clients, invoices, items/services, expenses, and payments.
---

# FreshBooks Accounting

FreshBooks is an invoicing and accounting platform aimed at service businesses and freelancers. API resources are scoped to an account/business ID resolved at runtime from the authenticated user's memberships.

Use together with the shared `accounting-tax-analyst` skill for role, output formats, and safety rules.

## Supported NoUI operations

### Read (perform when needed)

| Operation | Notes |
|---|---|
| List clients | FreshBooks calls customers "clients"; names, emails, organizations, outstanding balances |
| List invoices | Status (draft, sent, viewed, paid, overdue, partial), amounts, due dates |
| Get invoice | Full detail: lines, taxes per line, amount outstanding, payment status |
| List items/services | Billable items with rates |
| List expenses | Where the integration exposes them — categories, amounts, vendors |
| List payments | Payments and which invoices they apply to |

### Write (explicit user intent required)

| Operation | Confirmation required |
|---|---|
| Create client | Show details, confirm first |
| Create invoice | Show client, lines, amounts; create as draft; confirm first |
| Send invoice | Restate invoice number, recipient, amount; explicit "yes" |
| Record payment | Restate invoice, amount, date, method; explicit "yes" |

Deleting/voiding invoices, clients, or expenses is **not supported** by this skill. If a listed write operation turns out to be unavailable in the current integration, say so — don't simulate it.

## Safety requirements

- Resolve account/business ID from the authenticated session at runtime; never hardcode it.
- Client and item IDs must come from list responses in this session.
- FreshBooks tax is applied per line item; never guess tax names/rates — use existing ones observed on items or provided by the user.
- Report FreshBooks' computed totals and outstanding amounts, not your own recalculation (recalculate only to cross-check, and flag mismatches).

## Common workflows

- **Receivables review**: list invoices → group by status → overdue detail by client → standard summary.
- **Client + invoice creation**: check client exists → confirm details → create draft → report ID/number → send only on separate explicit request.
- **Expense snapshot** (for tax summaries): list expenses by category for the period; note that expense data may be incomplete if bank feeds aren't reconciled.

## Edge cases

- "Outstanding" vs "amount" differ on partially paid invoices — always report both.
- Recurring invoice profiles generate invoices; distinguish the profile from generated invoices.
- Multi-currency clients: invoice currency may differ from account base currency.
- Deep accounting features (journal entries, full chart of accounts) are limited compared to Xero/Odoo — state limits rather than approximating.

## Output

Follow the shared skill's output format. Identify records as `Invoice <number> (FreshBooks ID <id>)` using observed values.

---
name: wave-accounting
description: NoUI workflows for Wave Accounting — small-business invoicing and accounting. Use when the user's accounting platform is Wave, for businesses, customers, accounts, products, invoices, sending invoices, and recording payments.
---

# Wave Accounting

Wave is a free/low-cost accounting and invoicing platform for small businesses and freelancers. Its API is GraphQL-based; NoUI operations are scoped to a business.

Use together with the shared `accounting-tax-analyst` skill, which defines the analyst role, output formats, and safety rules.

## Supported NoUI operations

### Read (perform when needed)

| Operation | Notes |
|---|---|
| Get business | Business profile, currency, timezone — establish this first; most other calls need the business context |
| List customers | Names, emails, addresses, currency |
| List accounts | Ledger accounts (income, expense, asset, liability, equity) |
| List products | Products/services with default prices and income accounts |
| List invoices | Filterable by status; includes totals, amount due, due dates |
| Get invoice | Full detail: line items, taxes, payments applied, view/sent status |

### Write (explicit user intent required)

| Operation | Confirmation required |
|---|---|
| Create customer | Show name/email/details, confirm before creating |
| Create invoice | Show customer, line items, amounts, currency; create as draft; confirm before creating |
| Send invoice | Restate invoice number, recipient email, amount; explicit "yes" required |
| Record payment | Restate invoice, amount, date, payment account; explicit "yes" required |

Deleting or voiding invoices/customers is **not supported** by this skill.

## Safety requirements

- Resolve the business via "get business" at runtime; never hardcode business IDs.
- Customer and product IDs used in invoice creation must come from list/get responses in this session.
- Invoice amounts and line items come from the user or observed data — never invented.
- Wave computes invoice totals and taxes; report Wave's returned totals, not your own arithmetic.

## Common workflows

- **Receivables review**: get business → list invoices → group unpaid/overdue by customer → standard summary.
- **New invoice**: confirm customer exists (list customers; offer to create if missing — with confirmation) → confirm line items and amounts with user → create draft → report new invoice number → send only on a separate explicit request.
- **Payment recording**: get invoice → confirm amount due matches what the user says was paid → confirm payment account and date → record → report updated status.

## Edge cases

- A business may have multiple currencies across customers; flag mixed-currency totals.
- Draft invoices have no invoice number in some cases until approved/sent — refer to them by internal ID.
- Wave's expense-side coverage via NoUI may be limited; if asked for expense analysis, state what isn't available rather than approximating.
- Pagination: customer and invoice lists page; note when results are partial.

## Output

Follow the shared skill's output format. Identify records as `Invoice <number> (Wave ID <id>)` using observed values.

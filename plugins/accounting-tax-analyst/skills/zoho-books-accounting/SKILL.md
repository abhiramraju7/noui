---
name: zoho-books-accounting
description: NoUI workflows for Zoho Books — online accounting with customers, vendors, invoices, items, chart of accounts, payments, taxes, and reports. Use when the user's platform is Zoho Books.
---

# Zoho Books Accounting

Zoho Books is an online accounting platform within the Zoho suite. API resources are scoped to an organization ID resolved at runtime from the authenticated user's organizations.

Use together with the shared `accounting-tax-analyst` skill for role, output formats, and safety rules.

## Supported NoUI operations

### Read (perform when needed)

| Operation | Notes |
|---|---|
| List organizations | Establish org context first |
| List/get customers | Contacts with `contact_type=customer`; balances, currency |
| List/get vendors | Contacts with `contact_type=vendor` |
| List/get invoices | Status: draft, sent, overdue, paid, partially_paid, void; totals and balances |
| List items | Products/services with rates and tax preferences |
| List chart of accounts | Account types and balances where exposed |
| List customer/vendor payments | Payment records and invoice/bill applications |
| List taxes | Tax rates and tax groups — read-only for tax summaries |
| Reports | Where exposed: P&L, aged receivables/payables, tax reports |

### Write (explicit user intent required)

| Operation | Confirmation required |
|---|---|
| Create customer/vendor | Show details, confirm first |
| Create invoice | Create as draft; show customer, lines, taxes; confirm first |
| Send invoice (email) | Restate number, recipient, amount; explicit "yes" |
| Record payment | Restate invoice, amount, date, deposit account; explicit "yes" |

Voiding/deleting invoices or contacts, and creating/modifying taxes, are **not supported** by this skill by default.

## Safety requirements

- Resolve organization ID at runtime; never hardcode organization, customer, or account IDs.
- Item, tax, and account IDs used in writes must come from list responses in this session.
- Zoho Books enforces edition-specific tax handling (e.g., GST/VAT editions with mandatory fields); if required tax fields are unknown, ask the user rather than guessing.
- Report Zoho's computed `total`, `balance`, and status; if your recomputation disagrees, flag it as a finding.

## Common workflows

- **Books review**: list invoices by status → overdue by customer → vendor payables where used → standard summary.
- **Tax summary**: list taxes → group invoice lines/totals by tax → use tax reports where available → mandatory disclaimer.
- **Vendor/customer review**: list both contact types → duplicates by name/email → missing GST/VAT or contact fields.

## Edge cases

- Contacts have sub-contacts/contact persons; the primary email may live on a contact person record.
- Multi-branch/GST organizations may segment data by branch; note the branch scope if visible.
- Credit notes and retainer invoices affect balances; report separately if observed.
- Rate limits are per-organization and stricter than other platforms; batch reads sensibly and note if analysis was truncated.

## Output

Follow the shared skill's output format. Identify records as `Invoice <invoice_number> (Zoho ID <invoice_id>)` using observed values.

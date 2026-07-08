---
description: Review accounting data and produce a structured accounting summary (unpaid/overdue invoices, customer/vendor health, bookkeeping risks)
argument-hint: [platform or scope, e.g. "wave", "xero last quarter"]
---

# Accounting Review

Perform a read-only review of the user's accounting data and produce a structured summary.

Scope hint from user (may be empty): $ARGUMENTS

## Steps

1. **Identify the platform.** Determine which accounting platform is in use (Wave, FreshBooks, Xero, Zoho Books, or Odoo) from the user's request, connected tools, or available NoUI skills. If ambiguous, ask which platform to review before fetching data. Load the matching platform skill from this plugin for platform-specific guidance.
2. **Gather data (read-only).** Using only read operations:
   - Fetch business/organization context (business profile, base currency, fiscal settings where available).
   - List invoices; note status (draft, sent, paid, partially paid, overdue), amounts, currencies, and due dates.
   - List customers and (where supported) vendors.
   - List accounts / chart of accounts and products/items where supported.
3. **Analyze:**
   - Unpaid invoices: total count and amount, grouped by customer.
   - Overdue invoices: anything past due date as of today; compute days overdue.
   - Customer/vendor issues: missing emails or addresses, likely duplicates, customers with no activity.
   - Record consistency: invoices without customers, items without prices, uncategorized transactions, gaps in invoice numbering where observable.
   - Bookkeeping risks: stale drafts, negative balances, mismatched currencies, unusually large or round-number entries worth verifying.
4. **Report** using the standard output format below. Distinguish clearly between **observed data** (retrieved via the API) and **inferred conclusions** (your analysis). Never invent amounts, names, dates, or IDs — if a value could not be retrieved, say so.

## Safety

- This command is **read-only**. Do not create, modify, send, or delete anything.
- If a finding suggests a corrective write action (e.g., "send reminder for overdue invoice"), list it under **Actions Requiring Confirmation** — do not execute it.
- Never include credentials, tokens, or raw API keys in output.

## Output format

```md
## Summary

## Key Findings

## Open Invoices

## Overdue Items

## Tax-Relevant Notes

## Risks or Inconsistencies

## Recommended Next Steps

## Actions Requiring Confirmation
```

Omit sections with nothing to report, but always include Summary and Key Findings.

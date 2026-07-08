---
description: Reconciliation support — match invoices to payments, find unmatched or inconsistent entries, produce a reconciliation checklist
argument-hint: [scope, e.g. "June 2026", "customer Acme"]
---

# Reconcile Books

Support bookkeeping reconciliation by cross-checking invoices, payments, accounts, and customer/vendor records. **Read-only** — this command identifies discrepancies; it never fixes them automatically.

Scope hint (may be empty): $ARGUMENTS

## Steps

1. **Identify the platform** and load the matching platform skill from this plugin. If no period/scope is given, ask.
2. **Gather data (read-only):**
   - Invoices with status and amounts due/paid.
   - Payments (recorded payments, payment allocations) where the platform exposes them.
   - Account balances / chart of accounts where available.
   - Bills and journal entries (Odoo, Xero, Zoho Books) where available.
3. **Cross-check:**
   - **Unmatched payments**: payments not linked to an invoice, or linked amounts that don't sum to the payment total.
   - **Partially paid invoices**: paid amount vs. invoice total vs. status field consistency.
   - **Status inconsistencies**: invoices marked paid with outstanding balance, or unpaid with zero balance.
   - **Balance inconsistencies**: receivables per invoice list vs. receivables account balance where both are observable.
   - **Missing entries**: sent invoices with no receivable record, payments referencing missing customers/invoices, gaps in numbering sequences.
   - **Currency/date issues**: mixed currencies without noted rates, payment dates preceding invoice dates.
4. **Produce a reconciliation checklist**: one line per discrepancy with the record IDs/numbers involved, the observed values, and what a human should verify. State explicitly which checks could not be run because the platform doesn't expose the data.

## Output format

```md
## Summary

## Key Findings

## Reconciliation Checklist
- [ ] <item: records involved, observed values, what to verify>

## Risks or Inconsistencies

## Recommended Next Steps

## Actions Requiring Confirmation
```

## Safety

- Never adjust balances, re-link payments, edit invoices, or post journal entries. Every fix goes in the checklist or **Actions Requiring Confirmation** for the user to execute deliberately.
- Report only observed values with their source; mark any computed/derived figure as such.

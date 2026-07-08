---
description: Review customers and vendors — duplicates, incomplete contact details, transaction history, cleanup suggestions
argument-hint: [scope, e.g. "customers only", "vendors with no activity"]
---

# Vendor and Customer Review

Audit customer and vendor records for quality issues. **Read-only** — suggest cleanup actions; never apply them automatically.

Scope hint (may be empty): $ARGUMENTS

## Steps

1. **Identify the platform** and load the matching platform skill from this plugin. Note platform limits (e.g., Wave and FreshBooks NoUI surfaces are customer-centric; vendors are first-class in Xero contacts, Zoho Books, and Odoo partners).
2. **Gather data (read-only):**
   - List all customers with contact details.
   - List vendors/suppliers where supported.
   - Where available, sample transaction history per contact (invoice counts, totals, last activity).
3. **Analyze:**
   - **Duplicates**: same or near-identical names, matching emails, matching tax/registration numbers. Flag as *likely* duplicates — never assert without evidence, and never merge.
   - **Incomplete records**: missing email, billing address, tax number, or currency where those fields matter for invoicing/tax.
   - **Inactive or orphaned records**: contacts with no transactions; transactions referencing contacts you couldn't retrieve.
   - **Inconsistencies**: same contact with different currencies/addresses across records.
4. **Report**: for each issue, list the records involved (names + platform IDs as observed), the evidence, and a suggested cleanup action. Put every suggested change (merge, edit, archive) under **Actions Requiring Confirmation** — do not perform any of them from this command. Merging/archiving should be done by the user in the platform UI or via an explicitly confirmed follow-up.

## Output format

```md
## Summary

## Key Findings

## Likely Duplicates

## Incomplete Records

## Inactive / Orphaned Records

## Recommended Next Steps

## Actions Requiring Confirmation
```

## Safety

- Never create, edit, merge, archive, or delete contacts from this command.
- Contact details are personal data — include only what is needed to identify the record; do not dump full contact lists unless asked.

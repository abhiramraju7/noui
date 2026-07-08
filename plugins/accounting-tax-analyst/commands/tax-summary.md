---
description: Prepare a non-certified tax review summary — revenue, expenses, tax-relevant categories, and missing records
argument-hint: [period, e.g. "2026 Q2", "last fiscal year"]
---

# Tax Summary

Produce an operational tax review summary from the user's accounting data. **Read-only.**

Period/scope hint (may be empty): $ARGUMENTS

## Steps

1. **Clarify the period.** If no period is given, ask (e.g., current quarter vs. fiscal year) — tax summaries are meaningless without a defined period.
2. **Identify the platform** and load the matching platform skill from this plugin.
3. **Gather data (read-only):**
   - Invoices in the period: totals by status. Revenue = paid/receivable invoices per the platform's own figures.
   - Expenses/bills where the platform supports them (Xero, Zoho Books, Odoo, FreshBooks; Wave's NoUI surface may be receivables-focused — say so if expenses are unavailable).
   - Tax rates/tax codes applied to invoices and accounts where available.
   - Customer/vendor records referenced by those transactions.
4. **Analyze:**
   - Revenue summary by month and by customer; note currency mix.
   - Expense summary by category/account where supported.
   - Tax-relevant categories: taxed vs. untaxed line items, distinct tax rates in use, zero-rated or exempt items.
   - Gaps: invoices missing tax codes, customers missing tax/contact info (e.g., tax numbers, addresses needed for jurisdiction), uncategorized transactions, vendors without records for claimed expenses.
5. **Report** using the standard output format (Summary, Key Findings, Tax-Relevant Notes, Risks or Inconsistencies, Recommended Next Steps, Actions Requiring Confirmation). Label observed figures vs. inferred estimates. Never invent tax rates or amounts.

## Mandatory disclaimer

End every tax summary with:

> **Disclaimer:** This summary is for operational review only. It is not certified tax, accounting, or legal advice. Figures are drawn from the connected accounting platform and have not been independently audited. Consult a qualified tax professional before filing or making tax decisions.

## Safety

- Never create or modify tax records, tax rates, or filings from this command. If the user wants changes, direct them to `/invoice-workflow` or the platform UI, with explicit confirmation required.
- Do not guess jurisdiction-specific rules (rates, thresholds, deductibility). Report what the data shows; flag questions for a professional.

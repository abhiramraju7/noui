---
description: Invoice operations — list, inspect, draft, send, and record payments (writes require explicit confirmation)
argument-hint: [action, e.g. "list unpaid", "create invoice for Acme", "send #1042"]
---

# Invoice Workflow

Handle invoice-related tasks on the user's accounting platform (Wave, FreshBooks, Xero, Zoho Books, or Odoo).

Requested action (may be empty): $ARGUMENTS

## Steps

1. **Identify platform and intent.** Determine the platform and load the matching platform skill from this plugin. Classify the request as read (list/inspect) or write (create/send/record payment).
2. **Read operations** (perform freely when relevant):
   - List invoices, optionally filtered by status, customer, or date range.
   - Get full details of a specific invoice: line items, amounts, taxes, currency, due date, payment status.
   - Cross-reference the customer record for the invoice.
3. **Write operations** (each requires its own explicit confirmation):
   - **Create draft invoice**: only with user-provided or user-confirmed customer, line items, amounts, and currency. Never invent amounts, tax rates, or customer names. Create as *draft* unless the user explicitly asks otherwise. Show the exact invoice contents and get confirmation *before* creating.
   - **Send invoice**: only when the user explicitly asks to send a specific invoice. Restate invoice number, recipient, and amount, then require a clear "yes" before sending.
   - **Record payment**: only when the user explicitly asks. Confirm invoice, amount, date, and payment account/method first. Never guess the payment amount — ask if not stated.
4. **Never** delete or void invoices, modify sent invoices, or issue refunds/credit notes through this command. If asked, explain that destructive operations are out of scope by default and suggest doing it in the platform UI.
5. **Report** the outcome: what was read or changed (with IDs/numbers returned by the platform), and any follow-ups under **Actions Requiring Confirmation**.

## Confirmation pattern

Before any write, present:

```md
### Proposed action
- Operation: <create draft / send / record payment>
- Invoice: <number or "new draft">
- Customer: <name>
- Amount: <amount + currency>
- Details: <line items / payment method / date>

Proceed? (yes/no)
```

Only proceed on an unambiguous affirmative that refers to this specific action.

---
name: freshbooks-mark-payment
description: "Mark a FreshBooks invoice as paid by recording a payment against it. Use when the user wants to mark/record a payment, mark an invoice paid, log that a client paid, or settle an invoice in FreshBooks. Writes data. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — Mark Payment

Records a payment against an existing invoice for the authenticated FreshBooks
account, marking it paid (or partially paid). The single operation under
`operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP.
The FreshBooks accounting API (`api.freshbooks.com`) authenticates with a short-lived
in-memory **bearer token** (not cookies) and serves wildcard CORS, so the operation
sniffs the live bearer off a real request via CDP `Network` events and replays the call
with `credentials:'omit'`. The token is cached on disk until shortly before its JWT
`exp`. See `noui_runtime/freshbooks_auth.py`.

The invoice is given by **number** (e.g. `0000001`) or numeric id and resolved
automatically. The payment amount defaults to the invoice's **full outstanding
balance**, so a single call settles the invoice. The account id is resolved at runtime
(see `noui_runtime/freshbooks_account.py`).

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop via `chrome://inspect` (`localhost:9222`).
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.
3. The invoice must be finalized (Sent) and have an outstanding balance.

## Operation

### mark_payment — record a payment

```bash
# Pay an invoice in full (amount = outstanding balance, method Check)
.venv/bin/python operations/mark_payment.py --invoice 0000001

# Partial payment by bank transfer with a note
.venv/bin/python operations/mark_payment.py \
  --invoice 0000002 --amount 25 --type "Bank Transfer" --note "Deposit"

# Backdated cash payment
.venv/bin/python operations/mark_payment.py --invoice 0000003 --type Cash --date 2026-05-15
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--invoice` | yes | — | Invoice number (e.g. `0000001`) or numeric id. |
| `--amount` | no | full outstanding | Payment amount. |
| `--type` | no | `Check` | Payment method: Check, Cash, Credit, Bank Transfer, PayPal, Other. |
| `--date` | no | today | Payment date, `YYYY-MM-DD`. |
| `--note` | no | — | Note recorded on the payment. |
| `--currency-code` | no | `USD` | ISO currency code. |

**Returns**

```json
{
  "payment_id": 241727,
  "invoice_number": "0000001",
  "client": "d1",
  "amount": "540.00",
  "currency": "USD",
  "payment_type": "Check",
  "date": "2026-06-07",
  "invoice_status": "paid",
  "invoice_outstanding": "0.00"
}
```

## Notes

- **Writes data** — this records a real payment and changes the invoice's status.
- A full payment flips the invoice to `paid`; a partial payment leaves it `partial`
  with a reduced outstanding balance.
- Payments feed cash-basis reports and reduce the client's balance in the
  Accounts Receivable aging report (`freshbooks-reports` skill).
- If a call returns 401/403, the operation re-sniffs a fresh bearer once and retries.

---
name: freshbooks-clients
description: "List and create clients (customers) in FreshBooks. Use when the user wants to see/search existing clients or add a new client/customer/contact in FreshBooks. Reads and writes data. Requires an authenticated Tabby session for the `freshbooks` profile."
---

# FreshBooks — Clients

List and create clients for the authenticated FreshBooks account. Each operation
under `operations/` is a standalone CLI script that prints a JSON response to stdout.

## How it works

Execution runs **inside Tabby's authenticated FreshBooks browser session** via CDP.
The FreshBooks accounting API (`api.freshbooks.com`) authenticates with a short-lived
in-memory **bearer token** (not cookies) and serves wildcard CORS, so each operation
sniffs the live bearer off a real request via CDP `Network` events and replays the call
with `credentials:'omit'`. The token is cached on disk until shortly before its JWT
`exp`. See `noui_runtime/freshbooks_auth.py`.

## Prerequisites

1. **Tabby is running with the `freshbooks` profile, authenticated, with `my.freshbooks.com` open:**
   ```bash
   .venv/bin/python cli/main.py tabby session ensure --profile freshbooks
   ```
   FreshBooks enforces an email code on every new device, so the first login per
   session is human-in-the-loop via `chrome://inspect` (`localhost:9222`).
2. The Tabby session must have a page open on `my.freshbooks.com` at call time.

## Operations

### list_clients — list / search clients

```bash
# All clients
.venv/bin/python operations/list_clients.py

# Filter by name/organization/email
.venv/bin/python operations/list_clients.py --query "amazon"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--query` | no | — | Case-insensitive filter on name/organization/email. |
| `--page` | no | `1` | 1-based page number. |
| `--per-page` | no | `50` | Clients per page. |

### create_client — create a client

```bash
# Company with a contact + email
.venv/bin/python operations/create_client.py \
  --organization "Globex Corp" --first-name "Hank" --last-name "Scorpio" \
  --email "hank@globex.com" --country "United States" --city "Cypress Creek"

# Minimal (organization only)
.venv/bin/python operations/create_client.py --organization "Initech"
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--organization` | one of these | — | Company/organization name. |
| `--first-name` / `--last-name` | one of these | — | Contact name. |
| `--email` | no | — | Contact email. |
| `--currency-code` | no | `USD` | ISO currency code. |
| `--phone` | no | — | Contact phone. |
| `--city` | no | — | Billing city. |
| `--country` | no | — | Billing country. |

At least one of `--organization`, `--first-name`, or `--last-name` is required.

**Returns**

```json
{
  "id": 395260,
  "organization": "Globex Corp",
  "name": "Hank Scorpio",
  "email": "hank@globex.com",
  "currency": "USD",
  "country": "United States",
  "city": "Cypress Creek"
}
```

## Notes

- `create_client` **writes data** — it adds a real client to the account.
- The account ID is resolved at runtime from the authenticated login
  (see `noui_runtime/freshbooks_account.py`); set `FRESHBOOKS_ACCOUNT_ID` to override.
- New clients become valid `--client` targets for the `freshbooks-create-invoice` skill.
- If a call returns 401/403, the operation re-sniffs a fresh bearer once and retries.

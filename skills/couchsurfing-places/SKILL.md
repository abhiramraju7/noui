---
name: couchsurfing-places
description: Use when the user wants to discover public Couchsurfing destination pages or popular places. Uses Tabby execute/fetch and never exposes member profiles.
---

# Couchsurfing Places

Read Couchsurfing's public `/places/` catalogue through Tabby's `POST /execute/fetch` browser-session transport. No CDP, token extraction, or direct HTTP fallback is used.

Requires a HEALTHY `couchsurfing` Tabby profile and `TABBY_API_URL` plus Tabby client credentials.

## Operations

- `search_places --query <text> [--limit 10]`
- `list_popular_places [--limit 20]`

Only public catalogue data is returned. Host search, identities, messages, and member-only details require login and are intentionally excluded.

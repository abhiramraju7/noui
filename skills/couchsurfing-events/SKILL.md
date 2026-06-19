---
name: couchsurfing-events
description: Use when the user wants public Couchsurfing event links or details visible without member access.
---

# Couchsurfing Events

Read only publicly linked Couchsurfing events through Tabby's `POST /execute/fetch`. No CDP, token extraction, or private-event access is attempted.

## Operations

- `list_public_events [--query <text>] [--limit 20]`
- `get_event_details --url <couchsurfing-event-url>`

Requires a HEALTHY `couchsurfing` Tabby profile. Empty results mean events are not publicly linked on the current pages; the skill does not bypass login.

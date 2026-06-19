---
name: jumeirah-search
description: Use this skill when the user wants to find Jumeirah destinations or search Jumeirah hotels by destination and stay dates. Triggers on "search Jumeirah", "find Jumeirah hotels", "Jumeirah hotels in a city", "Jumeirah availability", or requests for public Jumeirah hotel listings. Uses the `jumeirah-hotels` Tabby profile and is not a generic hotel-search tool.
---

# Jumeirah Search

Search Jumeirah's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Jumeirah cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `jumeirah-hotels`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_hotels`

Return normalized Jumeirah hotel identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

Jumeirah embeds its regional booking catalogue in `__NEXT_DATA__`; the runtime parses the region, city, hotel ID, and hotel code hierarchy directly.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile jumeirah`.
- Booking property list missing — Jumeirah changed its `__NEXT_DATA__` layout; inspect the current page payload before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

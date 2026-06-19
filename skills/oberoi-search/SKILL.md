---
name: oberoi-search
description: Use this skill when the user wants to find Oberoi destinations or search Oberoi hotels by destination and stay dates. Triggers on "search Oberoi", "find Oberoi hotels", "Oberoi hotels in a city", "Oberoi availability", or requests for public Oberoi hotel listings. Uses the `oberoi-hotels` Tabby profile and is not a generic hotel-search tool.
---

# Oberoi Search

Search Oberoi's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Oberoi cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `oberoi-hotels`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_hotels`

Return normalized Oberoi hotel identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

Oberoi publishes hotel codes and cities in server-rendered `data-hotelcode` entries; the shared runtime parses those records directly.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile oberoi`.
- No hotel records — Oberoi changed its booking widget markup; inspect the current `data-hotelcode` entries before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

---
name: taj-search
description: Use this skill when the user wants to find Taj destinations or search Taj hotels by destination and stay dates. Triggers on "search Taj", "find Taj hotels", "Taj hotels in a city", "Taj availability", or requests for public Taj hotel listings. Uses the `taj-hotels` Tabby profile and is not a generic hotel-search tool.
---

# Taj Search

Search Taj's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Taj cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `taj-hotels`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_hotels`

Return normalized Taj hotel identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

Taj embeds destination inventory in `__NEXT_DATA__`; the shared runtime reads `destinationData[].participatingHotels` rather than driving visual controls.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile taj`.
- `__NEXT_DATA__` missing — Taj changed its server-rendered page; inspect the current destination HTML before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

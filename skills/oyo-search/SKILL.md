---
name: oyo-search
description: Use this skill when the user wants to find OYO destinations or search OYO hotels by destination and stay dates. Triggers on "search OYO", "find OYO hotels", "OYO hotels in a city", "OYO availability", or requests for public OYO hotel listings. Uses the `oyo` Tabby profile and is not a generic hotel-search tool.
---

# OYO Search

Search OYO's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies OYO cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `oyo`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_hotels`

Return normalized listings with availability, rating, amenities, discount, tax, and final quoted price. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

OYO embeds listing data in `window.__PRELOADED_STATE__`; the shared runtime parses that JSON rather than scraping visual text.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile oyo`.
- `__PRELOADED_STATE__` missing — OYO changed its server-rendered page; inspect the current listing HTML before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

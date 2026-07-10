---
name: banyan-tree-search
description: Use this skill when the user wants to find Banyan Tree Hotels destinations or search Banyan Tree Hotels properties by destination and stay dates. Triggers on "search Banyan Tree Hotels", "find Banyan Tree Hotels properties", "Banyan Tree Hotels properties in a city", "Banyan Tree Hotels availability", or requests for public Banyan Tree Hotels property listings. Uses the `banyan-tree` Tabby profile and is not a generic hotel-search tool.
---

# Banyan Tree Hotels Search

Search Banyan Tree Hotels' public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Banyan Tree cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `banyan-tree`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Bangkok" --limit 5
```

### `search_hotels`

Return normalized Banyan Tree Hotels property identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Bangkok" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

Banyan Tree pages can expose inventory in structured data and property links; the runtime normalizes those public records into hotel IDs, names, descriptions, ratings, and booking URLs.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile banyan-tree`.
- Empty property list — Banyan Tree Hotels changed its destination markup; inspect the current page payload before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

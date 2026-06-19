---
name: nh-hotels-search
description: Use this skill when the user wants to find NH Hotels destinations or search NH Hotels properties by destination and stay dates. Triggers on "search NH Hotels", "find NH Hotels properties", "NH Hotels properties in a city", "NH Hotels availability", or requests for public NH Hotels property listings. Uses the `nh-hotels` Tabby profile and is not a generic hotel-search tool.
---

# NH Hotels Search

Search NH Hotels' public inventory through Tabby's `POST /execute/fetch`. The browser session supplies NH cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `nh-hotels`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_hotels`

Return normalized NH Hotels property identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_hotels.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

NH Hotels embeds destination inventory in its server-rendered `beanDatalayer`; the runtime parses those hotel IDs, brands, and star ratings directly.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile nh-hotels`.
- `beanDatalayer` missing — NH Hotels changed its destination markup; inspect the current page payload before updating the parser.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

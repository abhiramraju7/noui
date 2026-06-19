---
name: sonder-search
description: Use this skill when the user wants to find Sonder destinations or search Sonder stays by destination and stay dates. Triggers on "search Sonder", "find Sonder stays", "Sonder stays in a city", "Sonder availability", or requests for public Sonder stay listings. Uses the `sonder` Tabby profile and is not a generic stay-search tool.
---

# Sonder Search

Search Sonder's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Sonder cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `sonder`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_stays`

Return normalized Sonder stay identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_stays.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

The runtime parses public structured data and property links returned inside the Tabby browser session.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile sonder`.
No results — verify the public search URL still returns structured data or property links.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

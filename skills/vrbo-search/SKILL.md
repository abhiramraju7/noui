---
name: vrbo-search
description: Use this skill when the user wants to find Vrbo destinations or search Vrbo stays by destination and stay dates. Triggers on "search Vrbo", "find Vrbo stays", "Vrbo stays in a city", "Vrbo availability", or requests for public Vrbo stay listings. Uses the `vrbo` Tabby profile and is not a generic stay-search tool.
---

# Vrbo Search

Search Vrbo's public inventory through Tabby's `POST /execute/fetch`. The browser session supplies Vrbo cookies and its normal TLS fingerprint; operations never connect through CDP or extract browser credentials.

## Prerequisites

- Keep an ACTIVE, HEALTHY Tabby session for profile `vrbo`.
- Configure `TABBY_API_URL`, `TABBY_CLIENT_ID`, and `TABBY_CLIENT_SECRET`.
- Run operations from this skill directory with Python 3.11+ and `httpx` installed.

## Operations

### `search_destinations`

Resolve cities and neighbourhoods before searching.

```bash
python operations/search_destinations.py --query "Hyderabad" --limit 5
```

### `search_stays`

Return normalized Vrbo stay identifiers, location metadata, and official booking URLs for the requested dates. Dates use `YYYY-MM-DD`.

```bash
python operations/search_stays.py \
  --destination "Hyderabad" \
  --check-in 2026-07-15 \
  --check-out 2026-07-17 \
  --rooms 1 --adults 2
```

The runtime parses public structured data and property links returned inside the Tabby browser session.

## Live-validation note

The local Tabby session received HTTP 429 from Vrbo during development. Operations report that status clearly; they do not fall back to CDP or direct HTTP.

## Troubleshooting

- `No healthy Tabby session` — run `noui tabby session ensure --profile vrbo`.
No results — verify the public search URL still returns structured data or property links.
- Empty first page — verify the destination spelling and dates, then use `search_destinations`.

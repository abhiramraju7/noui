---
name: expedia-stay-search
description: Use this skill when the user wants to search for hotels on Expedia by destination and dates, find available stays, check hotel pricing, or get a Hotel-Search URL. Triggers on "find a hotel", "search Expedia", "look up hotels in <city>", "book a stay", "hotel availability", or any request that implies Expedia stay search. Requires an authenticated Tabby browser session for the `expedia` profile; not usable as a generic hotel search tool for sites other than Expedia.
---

# Expedia Stay Search

Search Expedia for available hotels by destination and dates using an authenticated Tabby browser session. Returns a Hotel-Search URL and extracted listings (name, nightly price, total price, rating, reviews, refundable flag, link).

This skill uses Tabby's `POST /execute/fetch` and `POST /execute/browser` endpoints to drive the real Expedia site inside a Tabby-managed browser. That is intentional: Expedia sits behind Akamai, which blocks non-browser TLS fingerprints. Do not try to port the operations to `httpx` or `requests` — you will get 429 Too Many Requests.

## Prerequisites

Before invoking any operation:

1. **Tabby is running with the `expedia` profile.** Verify with `.venv/bin/python cli/main.py tabby session ensure --profile expedia` from the `noui/` directory. If that command fails, the user needs to re-run `/noui-record-login` for the `expedia` profile first — do not try to proceed without a live session.
2. **`PROFILE_SLUG=expedia` is exported** in the shell that runs the operation. This is the slug, not the DB UUID. The runtime reads it (or the `--profile-slug` flag) to identify the Tabby session.
3. **Agent credentials are configured.** `TABBY_CLIENT_ID` and `TABBY_CLIENT_SECRET` must be set in the environment or `.env` file. These are used to obtain a bearer token for the Tabby API.
4. **The Expedia profile is ACTIVE.** Check with the Tabby admin endpoint if in doubt — a STAGING profile returns 409 from the execute endpoints.

## Operations

### `search_hotels`

Search Expedia for hotels in a destination, on given check-in / check-out dates, for a given number of guests and rooms. Returns up to 25 listings extracted from the first page of results.

**When to use:** The user asks for hotel availability, prices, or a link to Expedia results for a specific city and date range.

**Command:**

```bash
python operations/search_hotels.py \
  --destination "Paris" \
  --check-in 2026-05-01 \
  --check-out 2026-05-04 \
  --guests 2 \
  --rooms 1
```

Prints a JSON object to stdout on success. Exits non-zero on failure with a diagnostic on stderr.

**Arguments:**

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--destination` | string | yes | — | City or place name. Expedia typeahead resolves it to a region ID. |
| `--check-in` | string | yes | — | `YYYY-MM-DD`. |
| `--check-out` | string | yes | — | `YYYY-MM-DD`. Must be after `--check-in`. |
| `--guests` | integer | no | `2` | Adult guests. |
| `--rooms` | integer | no | `1` | Number of rooms. |
| `--profile-slug` | string | no | `$PROFILE_SLUG` or `expedia` | Tabby profile slug. Override only if testing against a non-default profile. |

**Output shape:**

```json
{
  "search_url": "https://www.expedia.com/Hotel-Search?...",
  "destination": "Paris, France",
  "region_id": "178279",
  "check_in": "2026-05-01",
  "check_out": "2026-05-04",
  "guests": 2,
  "rooms": 1,
  "listings_count": 25,
  "listings": [
    {
      "name": "Hotel Le Example",
      "price_per_night": "$245",
      "price_total": "$735",
      "rating": "8.4/10",
      "rating_label": "Very Good",
      "reviews_count": "1,234",
      "refundable": true,
      "url": "https://www.expedia.com/..."
    }
  ]
}
```

## Troubleshooting

- **`No healthy Tabby session for profile "expedia"`** — no healthy session found. Run `tabby session ensure --profile expedia` and retry.
- **`Tabby execute/fetch failed (429)`** — Akamai is rate-limiting even through the browser. This is rare via the execute endpoint; if it happens repeatedly the Tabby session may need to rotate IPs or the profile needs re-recording.
- **Empty `listings`** — HAR capture did not find structured search results in the API responses, and the page summary fallback found no hotel headings. Expedia may have changed its API response shape. Check the HAR entries manually.
- **`TABBY_CLIENT_ID and TABBY_CLIENT_SECRET must be set`** — agent credentials are missing. Create an agent client in the Tabby admin UI and set the env vars.

## Notes

- This skill uses **HAR capture** during page navigation to intercept Expedia's API responses, then extracts hotel listings from the structured JSON data. Falls back to `get_page_summary` heading extraction if no structured API response is found.
- The `execute/fetch` endpoint runs `fetch()` inside the real browser — cookies and TLS fingerprint are preserved automatically.
- The `execute/browser` endpoint runs Playwright commands on the session page — no direct CDP WebSocket connection needed.
- A single invocation can take 10–20 seconds (typeahead + navigation + SPA render).
- This skill is the reference sample for the NoUI skills-generation pipeline. Generated skills from real recordings will share the same layout (`SKILL.md`, `operations/`, `noui_runtime/`, `manifest.json`, `auth_plan.json`) but will vary in operation count and complexity.

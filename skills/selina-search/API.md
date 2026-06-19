# Selina Search API

## `search_destinations`

Inputs: `query` (required), `limit=10`, `profile_slug="selina"`.

Returns normalized city/locality suggestions with IDs, display names, and coordinates.

## `search_stays`

Inputs: `destination`, `check_in`, `check_out` (required); `rooms=1`, `adults=2`, `children=0`, `profile_slug="selina"`.

Returns Selina public stay records, property links, and the official search URL for the requested dates.

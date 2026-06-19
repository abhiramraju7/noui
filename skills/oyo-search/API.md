# OYO Search API

## `search_destinations`

Inputs: `query` (required), `limit=10`, `profile_slug="oyo"`.

Returns normalized city/locality suggestions with IDs, display names, and coordinates.

## `search_hotels`

Inputs: `destination`, `check_in`, `check_out` (required); `rooms=1`, `adults=2`, `children=0`, `profile_slug="oyo"`.

Returns the OYO search URL and first-page hotel records with IDs, availability, rating, amenities, and public pricing fields.

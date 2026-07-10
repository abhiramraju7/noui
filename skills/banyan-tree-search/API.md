# Banyan Tree Hotels Search API

## `search_destinations`

Inputs: `query` (required), `limit=10`, `profile_slug="banyan-tree"`.

Returns normalized city/locality suggestions with IDs, display names, and coordinates.

## `search_hotels`

Inputs: `destination`, `check_in`, `check_out` (required); `rooms=1`, `adults=2`, `children=0`, `profile_slug="banyan-tree"`.

Returns Banyan Tree property IDs, brands, star ratings, and official booking URLs for the requested dates.

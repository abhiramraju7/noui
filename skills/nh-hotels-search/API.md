# NH Hotels Search API

## `search_destinations`

Inputs: `query` (required), `limit=10`, `profile_slug="nh-hotels"`.

Returns normalized city/locality suggestions with IDs, display names, and coordinates.

## `search_hotels`

Inputs: `destination`, `check_in`, `check_out` (required); `rooms=1`, `adults=2`, `children=0`, `profile_slug="nh-hotels"`.

Returns NH property IDs, brands, star ratings, and official booking URLs for the requested dates.

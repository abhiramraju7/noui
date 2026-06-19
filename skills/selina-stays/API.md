# Selina Stays API

All operations require `destination`, `stay_id`, `check_in`, and `check_out`; `profile_slug` defaults to `selina`.

- `get_stay_details` — normalized property, rating, amenity, availability, and pricing fields.
- `list_stay_amenities` — stay identity plus the published amenity names.
- `check_availability` — public availability flag and current base/tax/final quote.

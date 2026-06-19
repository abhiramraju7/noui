# OYO Pricing API

- `get_price_breakdown(destination, hotel_id, check_in, check_out)` — base, slashed, discount, tax, and final quoted values.
- `compare_hotel_prices(destination, check_in, check_out, limit=10)` — available first-page properties sorted by final quoted price.
- `list_discounted_hotels(destination, check_in, check_out, minimum_discount=20)` — properties meeting an advertised-discount threshold.

`profile_slug` is optional on every operation and defaults to `oyo`.

# Oberoi Pricing API

- `get_price_breakdown(destination, hotel_id, check_in, check_out)` — public amounts detected on the live booking page.
- `compare_hotel_prices(destination, check_in, check_out, limit=10)` — available properties sorted by lowest detected rate.
- `list_discounted_hotels(destination, check_in, check_out, minimum_discount=20)` — properties whose highest and lowest displayed rates differ by the requested percentage.

`profile_slug` is optional on every operation and defaults to `oberoi-hotels`.

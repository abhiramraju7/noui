---
name: oyo-pricing
description: Use this skill when the user wants to inspect OYO taxes, discounts, final quoted totals, compare OYO hotel prices, or find highly discounted OYO properties. Triggers on "OYO price breakdown", "OYO tax", "compare OYO prices", "cheapest OYO", or "OYO discounts". Uses the `oyo` Tabby profile.
---

# OYO Pricing

Read OYO's public pricing fields through Tabby's `POST /execute/fetch`. Values are returned exactly as quoted by OYO for the supplied search; the skill does not infer tax law or complete a booking.

## Prerequisites

- Keep an ACTIVE, HEALTHY `oyo` Tabby session and configure agent credentials.
- Use dates in `YYYY-MM-DD` format.

## Operations

```bash
python operations/get_price_breakdown.py \
  --destination Hyderabad --hotel-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/compare_hotel_prices.py \
  --destination Hyderabad \
  --check-in 2026-07-15 --check-out 2026-07-17 --limit 10

python operations/list_discounted_hotels.py \
  --destination Hyderabad \
  --check-in 2026-07-15 --check-out 2026-07-17 \
  --minimum-discount 40
```

The normalized price object contains `base_price`, `slashed_price`, `discount_percentage`, `tax_amount`, `total_with_tax`, and `currency`.

## Notes

- Prices and taxes are live quotes and can change between calls.
- OYO's quote semantics are preserved; do not label a value "per night" unless the source payload explicitly does so.
- `compare_hotel_prices` sorts available first-page properties by `total_with_tax`.

---
name: nh-hotels-pricing
description: Use this skill when the user wants to inspect live public NH rates, compare NH property prices, or find rate differences for a property. Triggers on "NH Hotels price breakdown", "compare NH Hotels prices", "cheapest NH Hotels", or "NH Hotels discounts". Uses the `nh-hotels` Tabby profile.
---

# NH Hotels Pricing

Read NH Hotels' public booking-page rates through Tabby's `POST /execute/fetch`. The skill reports only amounts present in the live response; it does not infer taxes or complete a booking.

## Prerequisites

- Keep an ACTIVE, HEALTHY `nh-hotels` Tabby session and configure agent credentials.
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

The normalized result contains `lowest_rate`, all detected `rates`, availability, currency, and the official booking URL.

## Notes

- Prices and taxes are live quotes and can change between calls.
- NH Hotels's quote semantics are preserved; do not label a value "per night" unless the source payload explicitly does so.
- `compare_hotel_prices` sorts available properties by their lowest detected public rate.

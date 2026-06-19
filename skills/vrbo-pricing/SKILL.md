---
name: vrbo-pricing
description: Use this skill when the user wants to inspect live public Vrbo rates, compare Vrbo stay prices, or find rate differences for a property. Triggers on "Vrbo price breakdown", "compare Vrbo prices", "cheapest Vrbo", or "Vrbo discounts". Uses the `vrbo` Tabby profile.
---

# Vrbo Pricing

Read Vrbo's public booking-page rates through Tabby's `POST /execute/fetch`. The skill reports only amounts present in the live response; it does not infer taxes or complete a booking.

## Prerequisites

- Keep an ACTIVE, HEALTHY `vrbo` Tabby session and configure agent credentials.
- Use dates in `YYYY-MM-DD` format.

## Operations

```bash
python operations/get_price_breakdown.py \
  --destination Hyderabad --stay-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/compare_stay_prices.py \
  --destination Hyderabad \
  --check-in 2026-07-15 --check-out 2026-07-17 --limit 10

python operations/list_discounted_stays.py \
  --destination Hyderabad \
  --check-in 2026-07-15 --check-out 2026-07-17 \
  --minimum-discount 40
```

The normalized result contains `lowest_rate`, all detected `rates`, availability, currency, and the official booking URL.

## Notes

- Prices and taxes are live quotes and can change between calls.
- Vrbo's quote semantics are preserved; do not label a value "per night" unless the source payload explicitly does so.
- `compare_stay_prices` sorts available properties by their lowest detected public rate.

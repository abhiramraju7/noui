---
name: taj-hotels
description: Use this skill when the user wants details, amenities, or availability for a specific Taj hotel. Triggers on "Taj hotel details", "Taj amenities", "is this Taj hotel available", or requests to inspect a hotel returned by `taj-search`. Uses the `taj-hotels` Tabby profile.
---

# Taj Hotels

Inspect a Taj hotel returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `taj-search` first to obtain `hotel_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `taj-hotels` Tabby session and configure agent credentials.

## Operations

```bash
python operations/get_hotel_details.py \
  --destination Hyderabad --hotel-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/list_hotel_amenities.py \
  --destination Hyderabad --hotel-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/check_availability.py \
  --destination Hyderabad --hotel-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17
```

`check_availability` reports Taj's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Hotel ... was not present` — search again or choose a hotel ID from the current destination results.
- Missing amenities — some Taj properties do not publish an amenity list in the listing payload.

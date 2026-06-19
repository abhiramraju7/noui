---
name: oberoi-hotels
description: Use this skill when the user wants details, amenities, or availability for a specific Oberoi hotel. Triggers on "Oberoi hotel details", "Oberoi amenities", "is this Oberoi hotel available", or requests to inspect a hotel returned by `oberoi-search`. Uses the `oberoi-hotels` Tabby profile.
---

# Oberoi Hotels

Inspect an Oberoi hotel returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `oberoi-search` first to obtain `hotel_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `oberoi-hotels` Tabby session and configure agent credentials.

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

`check_availability` reports Oberoi's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Hotel ... was not present` — search again or choose a hotel ID from the current destination results.
- Missing amenities — some Oberoi properties do not publish an amenity list in the listing payload.

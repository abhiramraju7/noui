---
name: oyo-hotels
description: Use this skill when the user wants details, amenities, or availability for a specific OYO hotel. Triggers on "OYO hotel details", "OYO amenities", "is this OYO hotel available", or requests to inspect a hotel returned by `oyo-search`. Uses the `oyo` Tabby profile.
---

# OYO Hotels

Inspect an OYO hotel returned on the first destination-results page. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `oyo-search` first to obtain `hotel_id` and confirm the property appears on the first page.
- Keep an ACTIVE, HEALTHY `oyo` Tabby session and configure agent credentials.

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

`check_availability` reports OYO's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Hotel ... was not present` — search again or choose a hotel ID from the current first-page results.
- Missing amenities — some OYO properties do not publish an amenity list in the listing payload.

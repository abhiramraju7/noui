---
name: hostelworld
description: Use this skill when the user wants details, amenities, or availability for a specific Hostelworld stay. Triggers on "Hostelworld stay details", "Hostelworld amenities", "is this Hostelworld stay available", or requests to inspect a stay returned by `hostelworld-search`. Uses the `hostelworld` Tabby profile.
---

# Hostelworld Stays

Inspect an Hostelworld stay returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `hostelworld-search` first to obtain `stay_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `hostelworld` Tabby session and configure agent credentials.

## Operations

```bash
python operations/get_stay_details.py \
  --destination Hyderabad --stay-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/list_stay_amenities.py \
  --destination Hyderabad --stay-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/check_availability.py \
  --destination Hyderabad --stay-id 330892 \
  --check-in 2026-07-15 --check-out 2026-07-17
```

`check_availability` reports Hostelworld's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Stay ... was not present` — search again or choose a stay ID from the current destination results.
- Missing amenities — some Hostelworld properties do not publish an amenity list in the listing payload.

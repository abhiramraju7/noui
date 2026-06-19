---
name: sonder
description: Use this skill when the user wants details, amenities, or availability for a specific Sonder stay. Triggers on "Sonder stay details", "Sonder amenities", "is this Sonder stay available", or requests to inspect a stay returned by `sonder-search`. Uses the `sonder` Tabby profile.
---

# Sonder Stays

Inspect an Sonder stay returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `sonder-search` first to obtain `stay_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `sonder` Tabby session and configure agent credentials.

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

`check_availability` reports Sonder's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Stay ... was not present` — search again or choose a stay ID from the current destination results.
- Missing amenities — some Sonder properties do not publish an amenity list in the listing payload.

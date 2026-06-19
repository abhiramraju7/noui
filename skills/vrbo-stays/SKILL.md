---
name: vrbo
description: Use this skill when the user wants details, amenities, or availability for a specific Vrbo stay. Triggers on "Vrbo stay details", "Vrbo amenities", "is this Vrbo stay available", or requests to inspect a stay returned by `vrbo-search`. Uses the `vrbo` Tabby profile.
---

# Vrbo Stays

Inspect an Vrbo stay returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `vrbo-search` first to obtain `stay_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `vrbo` Tabby session and configure agent credentials.

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

`check_availability` reports Vrbo's public sold-out flag and current quoted price. It does not reserve inventory.

## Live-validation note

The local Tabby session received HTTP 429 from Vrbo during development. Operations report that status clearly; they do not fall back to CDP or direct HTTP.

## Troubleshooting

- `Stay ... was not present` — search again or choose a stay ID from the current destination results.
- Missing amenities — some Vrbo properties do not publish an amenity list in the listing payload.

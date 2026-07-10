---
name: banyan-tree-properties
description: Use this skill when the user wants details, amenities, or availability for a specific Banyan Tree Hotels property. Triggers on "Banyan Tree Hotels property details", "Banyan Tree Hotels amenities", "is this Banyan Tree Hotels property available", or requests to inspect a hotel returned by `banyan-tree-search`. Uses the `banyan-tree` Tabby profile.
---

# Banyan Tree Hotels Properties

Inspect an Banyan Tree Hotels property returned by destination search. All operations use Tabby's `POST /execute/fetch`; there is no CDP connection, token sniffing, booking submission, or payment action.

## Prerequisites

- Run `banyan-tree-search` first to obtain `hotel_id` from the current destination results.
- Keep an ACTIVE, HEALTHY `banyan-tree` Tabby session and configure agent credentials.

## Operations

```bash
python operations/get_hotel_details.py \
  --destination Bangkok --hotel-id "https://www.banyantree.com/thailand/bangkok" \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/list_hotel_amenities.py \
  --destination Bangkok --hotel-id "https://www.banyantree.com/thailand/bangkok" \
  --check-in 2026-07-15 --check-out 2026-07-17

python operations/check_availability.py \
  --destination Bangkok --hotel-id "https://www.banyantree.com/thailand/bangkok" \
  --check-in 2026-07-15 --check-out 2026-07-17
```

`check_availability` reports Banyan Tree Hotels's public sold-out flag and current quoted price. It does not reserve inventory.

## Troubleshooting

- `Hotel ... was not present` — search again or choose a hotel ID from the current destination results.
- Missing amenities — some Banyan Tree Hotels properties do not publish an amenity list in the listing payload.

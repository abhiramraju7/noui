---
name: flydubai-pricing
description: "Search flydubai route availability and fare pricing. Use for flight calendar availability, fare and tax estimates, or one-way/round-trip pricing. Read-only — no booking."
---

# flydubai-pricing

Search flydubai route availability and fare pricing from stable public Flydubai web endpoints — no authentication required.

## When to use this skill

Use when the user wants to:

- Find cheaper dates on a flydubai route
- Check available fares for a route and date
- Compare one-way vs round-trip pricing
- Look up economy/business-class fare estimates

## Operations

### get_calendar — Route calendar availability

Returns Flydubai route calendar/schedule availability for an origin → destination pair.

```bash
python operations/get_calendar.py --origin DXB --destination CMB --from-date 2026-06-01
```

The response includes route metadata and available flight schedule dates.

### search_flights — Fare pricing for a specific date

Returns fare pricing for outbound and optional return flights.

```bash
# One-way
python operations/search_flights.py --origin DXB --destination BOM --depart-date 2026-08-15

# Round-trip
python operations/search_flights.py --origin DXB --destination KHI --depart-date 2026-09-01 --return-date 2026-09-08

# Exact dates only
python operations/search_flights.py --origin DXB --destination CMB --depart-date 2026-08-20 --exact-dates-only
```

Output includes:

- route
- direction
- departure date
- fare
- tax
- currency
- sold-out status

## Suggested workflow

1. Run `get_calendar` to inspect available dates for a route.
2. Run `search_flights` for specific travel dates.
3. Compare fare windows or exact-date pricing.

## Notes

- IATA airport codes are required, such as `DXB`, `BOM`, `KHI`, `CMB`.
- Dates must use `YYYY-MM-DD` format.
- `search_flights` supports one-way and round-trip pricing.
- `search_flights` may return nearby fare-window dates unless `--exact-dates-only` is used.
- No booking or checkout is performed — this skill is read-only.

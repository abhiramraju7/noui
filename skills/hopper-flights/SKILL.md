---
name: hopper-flights
description: Use when the user wants to search Hopper flights, inspect public flight results, or review publicly displayed airfares for a route and travel dates.
---

# Hopper Flights

Search Hopper public flight pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `hopper` profile plus Tabby API credentials.

```bash
python operations/run.py --origin "DEL" --destination "BOM" --departure 2026-08-10 --return-date 2026-08-12 --adults 1
```

Treat fares as public snapshots. Confirm baggage, fare rules, availability, and final price with the airline or booking provider.

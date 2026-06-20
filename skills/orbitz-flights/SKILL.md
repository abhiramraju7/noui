---
name: orbitz-flights
description: Use when the user wants to search Orbitz flights, inspect public flight results, or review publicly displayed airfares for a route and dates.
---

# Orbitz Flights

Search Orbitz public flight pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `orbitz` profile plus Tabby API credentials.

```bash
python operations/run.py --origin "DEL" --destination "BOM" --departure 2026-08-10 --return-date 2026-08-12 --adults 1
```

Treat fares as public snapshots. Confirm baggage, fare rules, availability, and final price with the airline or provider.

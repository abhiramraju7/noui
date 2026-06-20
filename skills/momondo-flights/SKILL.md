---
name: momondo-flights
description: Use when the user wants to search Momondo flights, inspect public flight results, or review publicly displayed airfares for a route and travel dates.
---

# Momondo Flights

Search Momondo public flight pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `momondo` profile plus Tabby API credentials.

```bash
python operations/run.py --origin "DEL" --destination "BOM" --departure 2026-08-10 --return-date 2026-08-12 --adults 1
```

Momondo localizes the public browser session by market; the runtime uses the active India origin for this profile. Search pages may return an empty server-rendered body while results load client-side, in which case the official search URL is preserved without fabricating fares.

Treat fares as public snapshots. Confirm baggage, fare rules, availability, and final price with the airline or booking provider.

---
name: trip-com-trains
description: Use when the user wants to search Trip.com trains, inspect public rail results, or review publicly displayed train fares for a route and dates.
---

# Trip.com Trains

Search Trip.com public train pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `trip-com` profile plus Tabby API credentials.

Trip.com currently wraps in-page fetch on some public routes; surface browser-fetch failures without switching to CDP or extracting tokens.

```bash
python operations/run.py --origin "London" --destination "Edinburgh" --departure 2026-08-10
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

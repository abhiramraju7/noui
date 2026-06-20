---
name: airbnb-homes
description: Use when the user wants to search Airbnb homes and vacation rentals, inspect public home and rental results, or review publicly displayed home prices for a destination and stay dates.
---

# Airbnb Homes

Search Airbnb public home and vacation-rental pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `airbnb` profile plus Tabby API credentials.

Airbnb currently wraps in-page fetch on some public routes; surface browser-fetch failures without switching to CDP or extracting tokens.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

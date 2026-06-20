---
name: priceline-cars
description: Use when the user wants to search Priceline rental cars, inspect public rental-car results, or review publicly displayed rental prices for pickup and drop-off locations.
---

# Priceline Cars

Search Priceline public rental-car pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `priceline` profile plus Tabby API credentials.

```bash
python operations/run.py --pickup "LAX" --dropoff "LAX" --departure 2026-08-10 --return-date 2026-08-12
```

Treat rental prices as public snapshots. Confirm taxes, mileage, deposit, availability, and cancellation terms with the provider.

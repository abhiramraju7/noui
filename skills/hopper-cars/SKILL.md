---
name: hopper-cars
description: Use when the user wants to search Hopper rental cars, inspect public car-rental results, or review publicly displayed car prices for pickup and drop-off locations.
---

# Hopper Cars

Search Hopper public car-rental pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `hopper` profile plus Tabby API credentials.

```bash
python operations/run.py --pickup "LAX" --dropoff "LAX" --departure 2026-08-10 --return-date 2026-08-12
```

Treat rental prices as public snapshots. Confirm taxes, fees, mileage, deposit, and cancellation terms with the provider.

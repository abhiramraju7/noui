---
name: trip-com-cars
description: Use when the user wants to search Trip.com rental cars, inspect public rental-car results, or review publicly displayed rental prices for pickup and drop-off locations.
---

# Trip.com Cars

Search Trip.com public rental-car pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `trip-com` profile plus Tabby API credentials.

Trip.com currently wraps in-page fetch on some public routes; surface browser-fetch failures without switching to CDP or extracting tokens.

```bash
python operations/run.py --pickup "LAX" --dropoff "LAX" --departure 2026-08-10 --return-date 2026-08-12
```

Treat rental prices as public snapshots. Confirm taxes, mileage, deposit, availability, and cancellation terms with the provider.

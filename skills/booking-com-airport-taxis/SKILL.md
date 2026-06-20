---
name: booking-com-airport-taxis
description: Use when the user wants to search Booking.com airport transfers, inspect public transfer results, or review publicly displayed transfer prices for airport and destination.
---

# Booking.com Airport Taxis

Search Booking.com public airport-transfer pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `booking-com` profile plus Tabby API credentials.

```bash
python operations/run.py --pickup "LHR" --dropoff "Central London" --departure 2026-08-10
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

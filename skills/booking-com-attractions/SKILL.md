---
name: booking-com-attractions
description: Use when the user wants to search Booking.com activities and experiences, inspect public activity and experience results, or review publicly displayed activity prices for a destination and dates.
---

# Booking.com Attractions

Search Booking.com public activity and experience pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `booking-com` profile plus Tabby API credentials.

```bash
python operations/run.py --destination "London" --departure 2026-08-10 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

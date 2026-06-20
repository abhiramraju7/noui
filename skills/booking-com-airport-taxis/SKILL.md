---
name: booking-com-airport-taxis
description: Use when the user wants to search Booking.com airport transfers, inspect public transfer results, or review publicly displayed transfer prices for airport and destination.
---

# Booking.com Airport Taxis

Search Booking.com public airport-transfer pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `booking-com` profile plus Tabby API credentials.

```bash
python operations/run.py --pickup "LHR" --dropoff "Central London" --departure 2026-08-10
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

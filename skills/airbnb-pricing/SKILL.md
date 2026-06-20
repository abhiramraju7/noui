---
name: airbnb-pricing
description: Use when the user wants to compare Airbnb public stay prices, inspect public provider offers, or review publicly displayed hotel prices for a destination and stay dates.
---

# Airbnb Pricing

Compare Airbnb public stay pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `airbnb` profile plus Tabby API credentials.

Airbnb currently wraps in-page fetch on some public routes; surface browser-fetch failures without switching to CDP or extracting tokens.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

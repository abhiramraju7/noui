---
name: priceline-cruises
description: Use when the user wants to search Priceline cruises, inspect public cruise results, or review publicly displayed cruise prices for destination and dates.
---

# Priceline Cruises

Search Priceline public cruise pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `priceline` profile plus Tabby API credentials.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

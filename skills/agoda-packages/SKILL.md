---
name: agoda-packages
description: Use when the user wants to search Agoda travel packages, inspect public flight-and-stay package results, or review publicly displayed package prices for a destination and dates.
---

# Agoda Packages

Search Agoda public package pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `agoda` profile plus Tabby API credentials.

Some Agoda routes leave results client-rendered; preserve the official source URL and never invent inventory.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

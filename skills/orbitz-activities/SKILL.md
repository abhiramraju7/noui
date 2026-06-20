---
name: orbitz-activities
description: Use when the user wants to search Orbitz activities and experiences, inspect public activity and experience results, or review publicly displayed activity prices for a destination and dates.
---

# Orbitz Activities

Search Orbitz public activity and experience pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `orbitz` profile plus Tabby API credentials.

```bash
python operations/run.py --destination "London" --departure 2026-08-10 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

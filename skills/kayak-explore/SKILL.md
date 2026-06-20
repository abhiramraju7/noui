---
name: kayak-explore
description: Use when the user wants to explore Kayak destinations, inspect public destination ideas and recent deals, or review publicly displayed recent travel prices for flexible discovery.
---

# Kayak Explore

Search Kayak public Explore pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `kayak` profile plus Tabby API credentials.

The public profile localizes to Kayak India; auth plans allow both canonical and localized domains.

```bash
python operations/run.py --origin "DEL" --query "beach"
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

---
name: google-travel-explore
description: Use when the user wants to explore Google Travel destinations, inspect public destination ideas and travel deals, or review publicly displayed travel prices for flexible destination discovery.
---

# Google Travel Explore

Search Google Travel public Explore pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `google-travel` profile plus Tabby API credentials.

```bash
python operations/run.py --query "beach trips from Delhi"
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

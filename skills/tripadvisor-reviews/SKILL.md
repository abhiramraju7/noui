---
name: tripadvisor-reviews
description: Use when the user wants to search Tripadvisor reviews and properties, inspect public ratings and review summaries, or read public traveler feedback for a destination and stay dates.
---

# Tripadvisor Reviews

Search Tripadvisor public property and review pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never use CDP, extract credentials, or fall back to direct target-site HTTP.

Requires a HEALTHY `tripadvisor` profile plus Tabby API credentials.

```bash
python operations/run.py --query "London hotels"
```

Reviews are public traveler contributions; preserve source URLs and do not imply verification beyond Tripadvisor metadata.

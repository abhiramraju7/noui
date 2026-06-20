---
name: skyscanner-explore
description: Use when the user wants to explore Skyscanner destinations, inspect public destination ideas and recent deals, or review publicly displayed recent travel prices for flexible discovery.
---

# Skyscanner Explore

Search Skyscanner public Explore pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `skyscanner` profile plus Tabby API credentials.

The public profile localizes to Skyscanner India; auth plans allow both canonical and localized domains.

```bash
python operations/run.py --origin "DEL" --query "beach"
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

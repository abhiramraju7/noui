---
name: agoda-homes
description: Use when the user wants to search Agoda homes and vacation rentals, inspect public home and rental results, or review publicly displayed home prices for a destination and stay dates.
---

# Agoda Homes

Search Agoda public home and vacation-rental pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `agoda` profile plus Tabby API credentials.

Some Agoda routes leave results client-rendered; preserve the official source URL and never invent inventory.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

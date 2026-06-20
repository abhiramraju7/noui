---
name: kayak-packages
description: Use when the user wants to search Kayak travel packages, inspect public flight-and-stay package results, or review publicly displayed package prices for a destination and dates.
---

# Kayak Packages

Search Kayak public package pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `kayak` profile plus Tabby API credentials.

The public profile localizes to Kayak India; auth plans allow both canonical and localized domains.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

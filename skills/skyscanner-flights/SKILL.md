---
name: skyscanner-flights
description: Use when the user wants to search Skyscanner flights, inspect public flight results, or review publicly displayed airfares for a route and dates.
---

# Skyscanner Flights

Search Skyscanner public flight pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `skyscanner` profile plus Tabby API credentials.

The public profile localizes to Skyscanner India; auth plans allow both canonical and localized domains.

```bash
python operations/run.py --origin "DEL" --destination "BOM" --departure 2026-08-10 --return-date 2026-08-12 --adults 1
```

Treat fares as public snapshots. Confirm baggage, fare rules, availability, and final price with the airline or provider.

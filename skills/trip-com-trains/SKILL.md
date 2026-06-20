---
name: trip-com-trains
description: Use when the user wants to search Trip.com trains, inspect public rail results, or review publicly displayed train fares for a route and dates.
---

# Trip.com Trains

Search Trip.com public train pages through Tabby `POST /execute/fetch`. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport tries `/execute/fetch`, then Tabby `/execute/browser` navigation with HAR capture, then guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is server-side Playwright, not client-side CDP.

Requires a HEALTHY `trip-com` profile plus Tabby API credentials.

Trip.com currently wraps in-page fetch on some public routes; surface browser-fetch failures without switching to CDP or extracting tokens.

```bash
python operations/run.py --origin "London" --destination "Edinburgh" --departure 2026-08-10
```

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

For a detail page or interactive filter flow, use `operations/browser.py`. It supports inspect, workflow, and discovery modes; bounded click/type/select/wait/scroll actions; optional screenshots; and HAR endpoint discovery. Transactional clicks remain blocked unless explicitly enabled.

For repeat checks, use `operations/snapshot.py --search-json '<json>'`. It creates a stable snapshot ID, can compare against prior JSON, reports added or removed prices, and optionally saves the current normalized result.

---
name: booking-com-stays
description: Use when the user wants to search Booking.com hotels, inspect public accommodation results, or review publicly displayed hotel prices for a destination and stay dates.
---

# Booking.com Stays

Search Booking.com public hotel pages through NoUI's hybrid runtime. Browser cookies and networking remain inside the Tabby session; never connect to a client-side CDP socket or extract credentials by default.

The default `auto` transport first tries `/execute/fetch`, then uses `/execute/browser` navigation with HAR capture for client-rendered pages, and finally tries guarded public HTTP. Force one path with `--transport fetch|browser|http`. Browser execution is Tabby-routed Playwright, not a client-side CDP connection.

Requires a HEALTHY `booking-com` profile plus Tabby API credentials.

```bash
python operations/run.py --destination "London" --check-in 2026-08-10 --check-out 2026-08-12 --adults 2
```

Browser fallback returns a bounded page summary plus discovered network request metadata. Use those request URLs to generalize stable JSON/GraphQL calls back onto `/execute/fetch`.

Treat prices as public snapshots. Confirm taxes, fees, availability, and cancellation terms on the selected booking provider before purchase.

For a detail page or interactive filter flow, use `operations/browser.py`. It supports inspect, workflow, and discovery modes; bounded click/type/select/wait/scroll actions; optional screenshots; and HAR endpoint discovery. Transactional clicks remain blocked unless explicitly enabled.

For repeat checks, use `operations/snapshot.py --search-json '<json>'`. It creates a stable snapshot ID, can compare against prior JSON, reports added or removed prices, and optionally saves the current normalized result.

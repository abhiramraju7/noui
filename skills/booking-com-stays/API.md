# Booking.com Stays API

`search_stays` accepts destination, check-in/check-out dates, adults, limit, and an optional Tabby profile slug. It returns the official source URL, normalized public records, visible prices, and a bounded page summary.

`transport` may be `auto`, `fetch`, `browser`, or `http`. Auto uses fetch → browser navigation with HAR capture → guarded public HTTP. Results include the selected transport, warnings, and bounded network-request metadata when browser capture is used.

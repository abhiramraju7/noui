# Booking.com Airport Taxis API

`search_airport_taxis` accepts pickup, drop-off, departure date, adults, limit, and an optional Tabby profile slug. It returns the official source URL, normalized public records, visible prices, and a bounded page summary.

`transport` may be `auto`, `fetch`, `browser`, or `http`. Auto uses fetch → browser navigation with HAR capture → guarded public HTTP. Results identify the chosen transport and include warnings plus bounded network-request metadata when browser capture is used.

`browser_booking_com_airport_taxis` accepts an allowlisted URL, mode (`inspect`, `workflow`, or `discover`), an optional JSON action array, screenshot flag, and explicit transactional-action flag. It returns page state, redacted action logs, visible prices, screenshot metadata, and prioritized HAR requests.

`snapshot_booking_com_airport_taxis` accepts search arguments as JSON plus optional previous snapshot JSON/path and output path. It returns a fingerprint, price additions/removals, result-count changes, and the current normalized snapshot.

# Skyscanner Cars API

`search_cars` accepts pickup and drop-off locations and dates, adults, limit, and an optional Tabby profile slug. It returns the official source URL, normalized public records, visible prices, and a bounded page summary.

`transport` may be `auto`, `fetch`, `browser`, or `http`. Auto uses fetch → browser navigation with HAR capture → guarded public HTTP. Results identify the chosen transport and include warnings plus bounded network-request metadata when browser capture is used.

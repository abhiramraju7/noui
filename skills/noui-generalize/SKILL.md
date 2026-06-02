---
name: noui-generalize
description: Use this skill when the user wants to generalize a recorded MCP workflow, rename tools to readable names, replace raw API params with natural-language parameters, fix bot detection issues (Akamai, Cloudflare, PerimeterX), rewrite operations to use browser execution, or make a generated MCP server usable by Claude Code. Triggers on "generalize a recorded workflow", "rename MCP tools", "replace raw API params with readable names", "make the MCP usable by Claude Code", "generalize tool signatures", "I can't use the MCP tools", "Akamai is blocking", "429 with valid cookies", "TLS fingerprinting", "execute fetch", "execute from inside the browser", "anti-bot workaround", "tabby credentials are empty", or "browser is authenticated but API calls fail".
---

# NoUI Generalize

Take a generated FastMCP server (or Skill) and make it **work** and **usable**:

1. **Execution strategy** — generated servers execute inside the Tabby browser via the `execute/fetch` endpoint by default (see `/noui-record-workflow` → *How Execution Works*). This skill handles the edge cases: sites requiring HITL login, profiles that need credential-type fixes, or rare cases where the `--execution-mode http` fallback is the right call.
2. **Interface cleanup** — replace raw internal API parameters (`f_sid`, `bl`, `reqid`) with natural-language names (`origin`, `destination`, `departure_date`) so Claude Code can invoke tools without domain knowledge.

**Prerequisite:** `/noui-record-workflow` must be complete and the MCP server must exist under `workbench/mcp_servers/`. For authenticated sites, `/noui-record-login` must also be complete with a running Tabby session.

---

## Works for both MCP and Skill outputs

The generalization logic is identical for either output format:

- **MCP output:** edit `workbench/mcp_servers/<app>/<server>/operations/<tool>.py` — the body of `async def execute(...)`. The FastMCP tool signature in `server.py` mirrors the execute() signature, so renaming params also requires updating the `server.py` decorator args.
- **Skill output:** edit `workbench/skills/<app>/operations/<tool>.py` — the body of `async def execute(...)` *and* the `_build_parser()` argparse registrations, because the skill operation is a standalone CLI script. The `SKILL.md` body's command examples also reference the flag names, so update them too (or regenerate SKILL.md by re-running `workflow export --as skill --description-override "..."`).

The Phase 0 execution diagnosis (bot detection, empty credentials, profile promotion) applies to both outputs unchanged. Note the default `tabby` execution mode uses `noui_runtime/execute.py` (`execute_fetch` → Tabby `/execute/fetch`); only the legacy `--execution-mode http` path uses `noui_runtime/auth.py` (`resolve_auth` → `/credentials/request`).

After generalizing a skill, use `/noui-generate-skill` (not `/noui-generate-mcp`) for install / test.

---

## Critical Rules (Never Violate)

- **NEVER** rewrite all tools at once — propose the new name and parameter list for each tool and get user approval before editing any files
- **ALWAYS** preserve existing execution mechanics (URL, method, headers, execute_fetch vs. httpx) unless deliberately switching modes — only the Python function interface changes
- **ALWAYS** hardcode values that were static in the recording (session routing params, build labels, `bl`, `f_sid`, `reqid`, `soc_app`, etc.) — do not expose infrastructure params to the caller
- **NEVER** ask questions that can be answered by reading the code or URL
- `httpx` only appears in generated operations when `--execution-mode http` was used explicitly. Default generated operations use `noui_runtime.execute.execute_fetch`. If you see `httpx` in a default-mode server, something is wrong.
- **ALWAYS** use the `execute_fetch` adapter for browser-side requests — it calls Tabby's `POST /execute/fetch` endpoint, which runs `fetch(url, {credentials: 'include'})` inside the real browser. Preserve this when hand-editing.
- **NEVER** assume "Login successful" in worker logs means login actually worked — CloakBrowser reports success when the DSL finishes, not when auth cookies appear. Always verify by checking cookies.
- After rewriting, always remind the user to restart Claude Code to reload the updated tools

---

## Phase 0 — Diagnose Execution Strategy

Before touching tool names or params, check whether the tools actually work.

### 0a. Find and test the server

```bash
ls -lt workbench/mcp_servers/
```

Run a quick end-to-end test:

```bash
.venv/bin/python -c "
import asyncio, json, sys
sys.path.insert(0, 'workbench/mcp_servers/<app_slug>/<server_id>')
from operations.<tool_name> import execute
async def test():
    result = await execute(...)  # fill in sample params
    print(json.dumps(result, indent=2)[:2000])
asyncio.run(test())
"
```

### 0b. Classify the result

| Result | Diagnosis | Next step |
|---|---|---|
| 200 with real data | Tool works — skip to Phase 2 (interface cleanup) |
| `No healthy Tabby session for profile` | Session not running or profile not HEALTHY | `tabby session ensure --profile <slug>` |
| `TABBY_CLIENT_ID and TABBY_CLIENT_SECRET must be set` | Agent credentials missing | Set `TABBY_CLIENT_ID` and `TABBY_CLIENT_SECRET` in `noui/.env` |
| CORS error / `credentials include not allowed` | Cross-origin fetch blocked | Re-export with `--execution-mode http` (error manifests as network error, not 403) |
| 429 / "Rate limited by Tabby API" | Per-profile rate limit hit | Wait and retry, or adjust `EXECUTE_RATE_LIMIT_PER_MIN` on the Tabby API |
| Server was generated with `--execution-mode http` and returns 429 | httpx blocked by TLS fingerprinting | Re-export without `--execution-mode http` to land on the execute-fetch default |
| Empty credentials / `name: ""` (http mode only) | Tabby credential_types format bug | Phase 1, Fix A |
| `No active profile found` (http mode only) | Profile still STAGING | Phase 1, Fix B |

### 0c. Confirm bot detection (if 429 with http mode)

Verify the browser itself can make the call via the execute endpoint:

```python
# Execute fetch from INSIDE the browser via Tabby's execute/fetch endpoint
import asyncio, json, httpx, os

async def test():
    # Get agent token
    api = os.environ.get("TABBY_API_URL", "http://localhost:8000")
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(f"{api}/auth/agent-token", json={
            "client_id": os.environ["TABBY_CLIENT_ID"],
            "client_secret": os.environ["TABBY_CLIENT_SECRET"],
        })
        token = token_resp.json()["access_token"]

        # Execute fetch inside the browser
        resp = await client.post(f"{api}/execute/fetch", json={
            "profile_id": "<profile_slug>",
            "url": "https://target-site.com/api/endpoint/test",
            "method": "GET",
        }, headers={"Authorization": f"Bearer {token}"})
        print(json.dumps(resp.json(), indent=2)[:2000])

asyncio.run(test())
```

If 200 from execute/fetch but 429 from httpx → **confirmed TLS fingerprinting**. The default execution mode (execute_fetch) already handles this. If the server was generated with `--execution-mode http`, re-export without that flag.

---

## Phase 1 — Fix Execution Strategy

### Fix A — credential_types format bug (legacy profiles only)

NoUI now emits `credential_types.cookies` in Tabby's required `[{name, volatility}]` object form (fixed at the source in `compiler/login/tabby_draft_generator.py` and `compiler/mcp/auth_plan.py`), so **fresh `login register` runs are already correct** — you should not need this fix on a newly registered profile.

It only applies to **profiles registered before that fix**, which stored `credential_types.cookies` as a plain string array (`["cookie_a", "cookie_b"]`). `credentials.service.ts` iterates cookies expecting objects with `.name`, so every cookie from such a profile comes back with empty name and value. (Only cookies are strict — Tabby tolerates header *names* as plain strings.) Remediate an affected legacy profile with:

```sql
-- Run from tabby/ directory:
-- docker compose exec -T postgres psql -U browser_hitl -d browser_hitl

-- Check current format:
SELECT credential_types FROM service_profiles WHERE profile_id = '<profile>';

-- Fix: convert each string to {name, volatility} object:
UPDATE service_profiles SET credential_types = '{
  "cookies": [
    {"name": "EG_SESSIONTOKEN", "volatility": "STABLE"},
    {"name": "bm_sz", "volatility": "VOLATILE"},
    {"name": "ak_bmsc", "volatility": "VOLATILE"},
    {"name": "user", "volatility": "STABLE"}
  ],
  "headers": []
}'
WHERE profile_id = '<profile>';
```

Mark cookies that rotate frequently (Akamai tokens: `bm_sz`, `ak_bmsc`, `bm_so`, `bm_s`, `_abck`) as `VOLATILE`. Everything else is `STABLE`.

### Fix B — Promote profile to ACTIVE

The credentials API (`POST /credentials/request`) only resolves `ACTIVE` profiles. Fresh registrations start as `STAGING`.

```sql
UPDATE service_profiles SET version_state = 'ACTIVE' WHERE profile_id = '<profile>';
```

### Fix C — Set refresh_interval_seconds

The keepalive runner defaults to 3600s between artifact re-exports. Set lower for faster credential refresh:

```sql
UPDATE applications
SET export_policy = export_policy || '{"refresh_interval_seconds": 60}'::jsonb
WHERE name ILIKE '%<app_name>%';
```

### Fix D — HITL login (when CloakBrowser fails)

If the automated login DSL can't complete (Akamai blocks form interactions), log in manually via the Tabby VNC/CDP screencast viewer, then force re-export:

```sql
UPDATE sessions SET artifacts_last_exported_at = NULL WHERE id = '<session_id>';
```

### Fix E — Execute-fetch is the default (no rewrite needed)

The execute-fetch adapter is now the **default** generated output. A recently
exported server already has operations that call `execute_fetch` from
`noui_runtime/execute.py`. If you are hand-editing or need to reason about the
pattern:

```python
from noui_runtime.execute import execute_fetch

result = await execute_fetch(
    "example-profile",                                # profile slug (set at compile time)
    "https://api.example.com/v1/items",
    method="POST",
    headers={"Accept": "application/json"},
    body={"name": "x"},                               # JSON-serialized automatically
)
```

`execute_fetch` calls Tabby's `POST /execute/fetch` endpoint, which runs
`fetch(url, {credentials: 'include'})` inside the real browser. The full
specification lives in `compiler/runtime/execute_adapter.py`.

**When you still need to re-generate or hand-edit:**

- The server was generated with `--execution-mode http` and keeps getting 429.
  → Re-export without the flag to land on the execute-fetch default.
- The API truly cannot be reached from the browser origin (CORS, or
  server-to-server endpoint). → keep `--execution-mode http` and fix the
  underlying auth / credential issue instead.

For the rationale (TLS fingerprinting, why browser-side execution, why
`credentials: 'include'`), see `/noui-record-workflow` → *How Execution Works*.

### DOM-scrape generalization (SPA-rendered content)

When data is rendered by client-side JS and not available as a JSON API, the
`execute_fetch` path won't work — you need to navigate and scrape the rendered
DOM. Use the Tabby `POST /execute/browser` endpoint via the generated
`execute_browser(profile_id, command, params)` helper, which provides
`navigate`, `get_page_summary`, and the other Playwright commands over HTTP.
`/execute/browser` is **live** today; the compiler does not auto-emit these
calls yet, so hand-wiring is still required — see the Expedia demo
(`operations/search_hotels.py`) for a working example.

Still, prefer discovering the underlying JSON API that the SPA consumes — it's
almost always there, and `execute_fetch` handles it cleanly.

> **Single browser instance caveat:** Tabby runs one CloakBrowser per session. Navigation changes the page — if keepalive actions need the homepage, coordinate or set keepalive to `dom_check` on `body` only.

---

## Phase 2 — Understand the Server

1. Read `tools.json` — note all tool names and their raw parameter names.

2. Read each `operations/<name>.py` — understand the call: URL, method, request body structure, which params are infrastructure vs. business inputs.

3. Ask the user:

> *"What workflow did you record? Describe in plain language what you were doing — for example: 'I searched for flights from Fortaleza to Seattle on June 1 for 1 adult'."*

Use the answer to anchor the business meaning of each tool.

---

## Phase 3 — Close Gaps Per Tool

For each tool, ask only the questions needed to understand which parameters carry business input:

- "Which parameter in this tool controls [the thing you described]? Do you know what value you used during recording?"
- "This tool posts to `[endpoint]` — is this the main [action]? What inputs does it need from the user?"
- For opaque bodies: "The request body appears to be binary-encoded. Based on what you described (origin, destination, date), which of these raw params do you think carries each value?"

Skip questions that are answerable from the URL path, parameter names, or values visible in the code.

---

## Phase 4 — Rewrite Tools One at a Time

For each tool, follow this sequence:

### 4a. Propose

Show the user the proposed new interface before touching any files:

```
Tool: create_data_batchexecute
New name: search_flights
New parameters:
  - origin: str          # IATA code or city name (e.g. "FOR", "Fortaleza")
  - destination: str     # IATA code or city name (e.g. "SEA", "Seattle")
  - departure_date: str  # Date in YYYY-MM-DD format
  - passengers: int = 1  # Number of passengers

Hardcoded (from recording):
  - f_sid: "<value from recording>"
  - bl: "<value>"
  - reqid: <value>
  - soc_app: <value>

Execution: execute_fetch / httpx (state which)

Approve this? (yes / adjust: ...)
```

### 4b. Edit on approval

Once approved, make four edits:

1. **`operations/<old_name>.py`** — rewrite the function signature and body:
   - New function name matches the approved tool name
   - New parameters are natural-language (`origin`, `destination`, etc.)
   - Infrastructure params are hardcoded as local variables
   - Build the raw request from the natural params (string formatting, encoding)
   - Use execute_fetch if Phase 1 flagged bot detection; otherwise preserve the existing HTTP call

2. **`tools.json`** — update the entry:
   - `name` → new tool name
   - `description` → plain-English description of what it does
   - `parameters` → updated list with natural-language names, types, descriptions

3. **`server.py`** — update the import and tool registration to use the new function name (if the function was renamed)

4. **`API.md`** — refresh the documentation:

```bash
.venv/bin/python cli/main.py mcp docs <server_id>
```

This overwrites `API.md` from the current `tools.json`. Run it after every tool edit, not just at the end.

### 4c. Move to next tool

Repeat Phase 4 for each tool. Do not batch edits.

---

## Phase 5 — Iterate After Testing

After all tools are rewritten, do a final docs refresh:

```bash
.venv/bin/python cli/main.py mcp docs <server_id>
```

Then tell the user:

> "Done. `API.md` is up to date. Please restart Claude Code (close and reopen, or run `/reconnect`) to reload the updated tools. Then try invoking the workflow — for example: 'search for flights from Fortaleza to Seattle on June 1'."

When the user reports results, fix any issues:

| Problem | Fix |
|---|---|
| Wrong parameter mapping | Re-read the operation, ask clarifying question, re-propose |
| Missing required parameter | Add it to signature and body |
| Tool call fails with HTTP error | Read the error body, compare to original recording values |
| Body encoding wrong | Check if original body was URL-encoded, JSON, or protobuf — reconstruct accordingly |
| 429 from tool call on a default-mode server | Verify Tabby has a healthy session for the profile; if yes, the account may be flagged — redo HITL login (Phase 1, Fix D) |
| 429 from tool call on `--execution-mode http` server | Re-export without the flag to use the execute-fetch default |
| `No healthy Tabby session for profile` | Tabby session not running — `tabby session ensure --profile <slug>` |
| `fetch()` returns 403 inside browser | Session expired — redo HITL login (Phase 1, Fix D) |

Keep iterating until the user can successfully invoke the workflow using natural language.

---

## What to Hardcode vs. Expose as Parameters

| Hardcode | Expose as parameter |
|---|---|
| `f_sid`, `bl`, `reqid`, `soc_app` | Origin, destination, dates |
| Build labels, session routing tokens | Search inputs (keywords, quantities) |
| CSRF tokens captured during recording | Filters (cabin class, stops) |
| App version identifiers | User preferences the tool is supposed to accept |
| Infrastructure headers (`x-goog-ext-*`) | Any value that changes meaningfully per call |

When in doubt: if the value was the same every time during recording and doesn't carry user intent, hardcode it.

---

## Dynamic-Header-Injection Sites (JS-injected auth)

Some SPAs acquire a short-lived bearer token in-memory (fetch from `/auth/init` or similar on page load), then wrap `window.fetch` / `XMLHttpRequest` with an interceptor that sets `Authorization: Bearer <jwt>` right before every XHR. The cookie jar is **empty** of auth material, `localStorage` / `sessionStorage` don't hold the bearer either, yet every real API call carries it. Calling the API via `execute_fetch` with `credentials: 'include'` alone will get you a 401 or 403.

### Detect

- HAR contains an `Authorization: Bearer eyJ...` header whose JWT `jti` (or `sub`, `exp`) rotates between recordings of the same flow.
- `document.cookie` at runtime does **not** include the bearer substring.
- `localStorage` and `sessionStorage` dumps don't contain the bearer either.
- The recorded API host is on a different subdomain from `www.*` (e.g. `api-prod-*`, `api.*`).

### Workaround — Sniff the Authorization header

The bearer token must be captured from the browser at runtime. Use the **live** `POST /execute/browser` endpoint via `execute_browser(profile_id, "get_page_summary", ...)` or a targeted JS eval to read it from the page.

Reference implementation (10-line core):

```python
await ws.send({"id": 1, "method": "Network.enable"})
await ws.send({"id": 2, "method": "Page.reload"})
deadline = loop.time() + 20
while loop.time() < deadline:
    msg = json.loads(await ws.recv())
    if msg.get("method") != "Network.requestWillBeSent":
        continue
    url = msg["params"]["request"].get("url", "")
    if TARGET_HOST not in url:
        continue
    authz = {k.lower(): v for k, v in msg["params"]["request"].get("headers", {}).items()}.get("authorization", "")
    if authz.startswith("eyJ"):
        return authz
```

See `.claude/skills/indigo-flight-search/noui_runtime/indigo_auth.py` for the full cache + retry wrapper around this core. The IndiGo skill is the canonical example of this pattern in this repo.

> **Forward pointer:** When the retro-C1 generic `sniff_headers()` helper lands in `noui_runtime`, delete the hand-written module and replace the import. See `plans/noui/noui-agent-friction-retro-plan.md` Section C1.

### Per-host static client IDs

Sites of this shape often pair the dynamic JWT with a stable `user_key` / `x-api-key` / `x-client-id` header that is **per-host but constant across sessions** (look for the same value across every request to that host in the HAR). Hardcode those — they're infrastructure, not user input.

---

## Known Anti-Bot Sites

| Site | Bot Detection | CloakBrowser Login | Workaround |
|---|---|---|---|
| Expedia | Akamai Bot Manager | Form blocked silently; reaches homepage but can't submit | HITL login + execute_fetch |
| Generic SPA with JS-injected auth | Token not in cookies/localStorage; `Authorization` is set by a fetch interceptor in the page's JS bundle | n/a (site may be anonymous) | Sniff the `Authorization` at runtime — see *Dynamic-Header-Injection Sites* above. |
| IndiGo (`api-prod-*-skyplus6e.goindigo.in`) | Anonymous session; per-host `user_key` + rotating JWT; Akamai cookies | n/a | Hardcode per-host `user_key`s; sniff JWT at runtime. Reference: `indigo-flight-search` skill. |

---

## Architecture Notes

- **Why cookies alone fail:** Akamai fingerprints the TLS ClientHello, HTTP/2 settings frame, header order, and other transport-layer signals. `httpx`/`curl` have distinctly different fingerprints from Chrome, even with identical cookies.
- **Why browser-side execution works:** The Tabby worker runs `fetch()` inside the real Chrome process via `page.evaluate()`. The HTTP request goes through Chrome's network stack with its native TLS implementation and fingerprint. No WebSocket or CDP port exposure needed — the Tabby API routes the request to the worker pod.
- **Single browser instance:** Tabby runs one CloakBrowser per session. Navigation changes the page for that session — if keepalive needs the homepage, set keepalive health checks to `dom_check` on `body` rather than URL-based checks.

---

## Decision Flow

```
Start
  │
  Phase 0: Test the tool as-is
  │
  ├─ Works (200 with data)?
  │     └─ Skip to Phase 2 (interface cleanup)
  │
  ├─ "No Tabby page matching <domain>"?
  │     └─ Open the site in Tabby, or `tabby session ensure --profile <id>`
  │
  ├─ CORS / cross-origin error?
  │     └─ Re-export with `--execution-mode http`
  │
  ├─ 429 on a default-mode server?
  │     └─ Phase 1: Fix D (HITL re-login) — the session or account is flagged
  │
  ├─ 429 on an `--execution-mode http` server?
  │     └─ Re-export without the flag to land on the execute-fetch default
  │
  ├─ Empty credentials / name: "" (http mode)?
  │     └─ Phase 1: Fix A (credential_types format)
  │
  ├─ "No active profile" (http mode)?
  │     └─ Phase 1: Fix B (promote to ACTIVE)
  │
  ├─ Login didn't actually work?
  │     └─ Phase 1: Fix D (HITL login)
  │
  ├─ 401/403 on default-mode server, cookies appear correct?
  │     └─ Check HAR: is `Authorization` present and does its JWT `jti` rotate across recordings?
  │         └─ Yes → Dynamic-header-injection pattern; see *Dynamic-Header-Injection Sites* section
  │
  Phase 2: Read tools.json + operations + ask user about workflow
  │
  Phase 3: Close gaps per tool (targeted questions only)
  │
  Phase 4: Rewrite tools one at a time (propose → approve → edit)
  │
  Phase 5: Test, iterate, remind user to restart Claude Code
```

---

## Related Skills

- `/noui-record-login` — Record login and register with Tabby (run first for authenticated sites)
- `/noui-record-workflow` — Record and export the workflow (run first to generate the server)
- `/noui-generate-mcp` — Server lifecycle after generalization (start/stop/connect to Claude Code)

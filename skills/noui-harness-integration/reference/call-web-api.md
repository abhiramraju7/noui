# The call_web_api tool contract

Ground truth: `adoptai-workflows` branch `feat/agent-harness-web-api-tool` (2026-06-11). Schema: `src/workflows/agent_harness/constants.py:936-991`. Dispatch: `activities.py:2376-2527` (`_dispatch_call_web_api`). Tabby client: `tabby_client.py`.

## What it is

The harness's only authenticated HTTP path. The agent (LLM) calls it as a tool; the **worker activity** executes it: mints Tabby tokens, POSTs Tabby `/execute/fetch`, and returns the response text. The request runs as `fetch()` inside the signed-in member's live Tabby browser session — real browser TLS, real session cookies.

It is **not** reachable from sandbox code. There is no URL, port, or credential inside the sandbox that a script could use. This is by design: tokens never enter the sandbox, the transcript, or Temporal history.

## Parameters

| Param | Required | Notes |
|---|---|---|
| `app` | yes | Tabby profile id/name — the NoUI `profile_slug`. Resolved server-side per member |
| `url` | yes | Absolute **HTTPS-only** URL (`activities.py:2418` rejects http) |
| `method` | no | GET (default), POST, PUT, PATCH, DELETE, HEAD |
| `headers` | no | string→string map. Browser adds session cookies itself — don't put auth here |
| `body` | no | string; JSON-encode object payloads |
| `wait_for_login` | no | Set `true` ONLY on retry after a `login_required` outcome |

There is **no URL allowlist** — gating is member identity + the Tabby profile ACL (`allowed_profiles` on the harness agent client) + HTTPS.

## Outcomes

| Outcome | Trigger | What the agent should do |
|---|---|---|
| `ok` | 200 from the fetch | Use the body. Truncated past `AGENT_HARNESS_TABBY_RESULT_CAP_CHARS` (default 20 000 chars) |
| `login_required` | no live session (Tabby 404/409) | Show the returned `login_url` (10-min short-link) to the user; retry the **same call** with `wait_for_login: true` — the worker then polls `/agent/session-status/{profile}` every 5 s up to `AGENT_HARNESS_TABBY_LOGIN_WAIT_SECONDS` (default 180) |
| `login_timeout` | user didn't finish login in the window | Not an error — ask the user to finish logging in, retry |
| `forbidden` | profile not in the agent client's `allowed_profiles` (Tabby 403) | Not retryable from the conversation; an admin must fix the profile/ACL |
| error ToolResult | transport/5xx/malformed JSON | Reported with detail (TabbyError surfacing, commit 665a4e4c) |

## Identity chain (who the call runs as)

1. adoptwebui validates the member's magic-link session and injects `member: {member_id, email}` into the turn payload (`adoptwebui backend/app/routes/end_user_agent_harness.py:221-228`). Workflows trusts this only over the `X-Workflows-Secret` channel.
2. The workflow threads `member` into tool dispatch; the activity refuses `call_web_api` without it.
3. The worker mints an **agent token** (`POST /auth/agent-token` with `AGENT_HARNESS_TABBY_CLIENT_ID/SECRET`, cached process-wide) and exchanges it for a **per-member user token** (`POST /auth/token-exchange`, keyed by member email, 15-min TTL cache) — `tabby_client.py:100-158`.
4. `/execute/fetch` runs with the user token + `profile_id=app`. Per-member session resolution / App-Template auto-provisioning happens Tabby-side (see /noui-tabby-integration).

So: the call is **member-scoped** (each member's own session and cookies), and the webui's `tabby_resolution_service` is *not* involved in this path.

## Harness-side configuration

| Env var | Default | Meaning |
|---|---|---|
| `AGENT_HARNESS_TABBY_API_URL` | — (gates the tool on/off) | Tabby base URL |
| `AGENT_HARNESS_TABBY_CLIENT_ID` / `_SECRET` | — | Agent client credentials for token minting |
| `AGENT_HARNESS_TABBY_LOGIN_WAIT_SECONDS` | 180 | `wait_for_login` polling deadline |
| `AGENT_HARNESS_TABBY_RESULT_CAP_CHARS` | 20 000 | Response truncation cap |

## What it cannot do (the platform gap register)

Tracked in `plans/adoptai-workflows/agent-harness-call-web-api-gaps.md`:

- **G1 — static secrets:** no server-side secret injection; an API-key header would transit model context. Static-key workflows stay on the classic path.
- **G2 — binary/large responses:** text-only, hard-capped. No PDF/file downloads through this tool.
- **G3 — page origin:** the fetch runs in the profile's *current* page; cross-origin targets 502. No navigation control is exposed — the profile's login DSL must end on the target origin.
- **G4 — profile reachability:** profile must be ACTIVE + in `allowed_profiles`; per-member sessions need App-Template auto-provisioning.
- **G5 — catalog cache window:** unrelated to the tool itself but hits publish flows (~30 s per-process staleness).

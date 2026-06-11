---
name: noui-harness-integration
description: Use this skill to understand how NoUI-generated skills run inside the Adopt Agent Harness — why direct Tabby calls are forbidden there, how the harness-side call_web_api tool routes authenticated requests through the member's browser session, what a harness-mode skill looks like (operation cards + operations.json, no transport code), and how to export one with execution_mode="harness". Triggers on "agent harness", "call_web_api", "export a skill for the harness", "harness execution mode", "skill can't call Tabby", "harness skill auth", "login_required wait_for_login", "harness sandbox", "member token minting", "harness skill catalog", or "upload a skill to the harness". Reference skill — read the linked docs in reference/ on demand.
---

# NoUI ↔ Agent Harness Integration

The **Adopt Agent Harness** (`adoptai-workflows/src/workflows/agent_harness/`) is a Temporal-orchestrated, Claude-driven agent runtime: per-conversation OpenSandbox container, S3-backed skill store, Redis-streamed events. It consumes Anthropic-format Agent Skills — the same on-disk shape NoUI generates. But it executes them under a **completely different transport model** than NoUI's classic skills, and skills exported the classic way will not work there.

**The inversion in one sentence:** a classic NoUI skill *is* the transport (its `operations/*.py` mint a Tabby token and call `/execute/fetch` themselves); in the harness, the **agent (LLM) is the transport** — it calls the harness-side `call_web_api` tool, the worker mints a per-member Tabby token, and the sandbox never sees a credential or a Tabby URL.

NoUI targets this environment with `noui workflow export --as skill --execution-mode harness`, which emits **operation cards** (per-operation `call_web_api` invocations in SKILL.md + machine-readable `operations.json`) and **no transport code** — no `noui_runtime/`, no `operations/*.py`, no `.venv`.

> **Ground truth + version caveat.** Everything here is grounded in `adoptai-workflows` and `adoptwebui` on branch `feat/agent-harness-web-api-tool` (verified 2026-06-11), cited as `path:line`. The harness evolves fast — re-verify line numbers against the branch you're running before trusting them blindly.

---

## Read this when

- You are exporting a recorded workflow as a skill that the Agent Harness will run.
- A generated skill works locally but fails inside the harness (no credentials, no Tabby URL, no Python deps).
- You need the `call_web_api` contract: parameters, outcome statuses, the `login_required` → `wait_for_login` HITL loop, response caps.
- You're debugging `forbidden`, `login_timeout`, truncated responses, or 502 "Failed to fetch" from harness conversations.
- You're deciding whether an operation should use `call_web_api` or plain sandbox `curl`.

---

## The model in 90 seconds

Identity and transport chain for one authenticated call:

```
member (magic-link session, adoptwebui)
  └─ webui harness proxy injects member:{member_id,email} into the turn payload
       (backend/app/routes/end_user_agent_harness.py:221-228)
        └─ AgentHarnessTurnWorkflow threads member to tool dispatch
             └─ agent calls call_web_api(app, url, method, headers, body)
                  └─ worker activity mints: agent token (/auth/agent-token)
                     → per-member token (/auth/token-exchange, email-keyed, 15-min cache)
                     → POST /execute/fetch with profile_id=app
                       (activities.py:2376-2527, tabby_client.py)
                        └─ Tabby executes fetch() inside the member's live browser session
```

Hard invariants that follow:

| Invariant | Consequence for NoUI skills |
|---|---|
| `call_web_api` runs **worker-side**; only the LLM can invoke it | Skill scripts in the sandbox can never make authenticated Tabby calls — ship *recipes*, not transport code |
| Tokens live only in worker memory | No env vars, no `.env`, no `resolve_auth()` — nothing to configure |
| Sandbox `env=None`, image `python:3.11-slim` (sandbox.py:121-139) | No `uv`, no venv provisioning, no `httpx`; post-processing scripts must be stdlib-only |
| Sandbox egress is open but **unauthenticated** | Public endpoints can use plain `curl`; anything session-bound must go through `call_web_api` |
| Results are text, capped at ~20k chars (`AGENT_HARNESS_TABBY_RESULT_CAP_CHARS`) | Paginate; never fetch binaries through `call_web_api` |
| Login recovery is built in (`login_required` → link → `wait_for_login: true`) | Skills need no session-ensure prerequisites — drop the `tabby session ensure` mechanics entirely |

→ Full detail in **[reference/call-web-api.md](reference/call-web-api.md)** and **[reference/harness-runtime.md](reference/harness-runtime.md)**.

---

## Reference docs (read on demand)

| Doc | Covers |
|---|---|
| **[reference/harness-runtime.md](reference/harness-runtime.md)** | The harness runtime a skill author must respect: sandbox anatomy (image, env, /workspace conventions, timeouts), the agent's full tool inventory, the S3 skill store (layout, resolution precedence, org-override-is-total, upload validation, cache TTLs). |
| **[reference/call-web-api.md](reference/call-web-api.md)** | The `call_web_api` tool contract: schema, the four outcome statuses, the login HITL state machine, token minting + member identity chain, config env vars, and what it cannot do (binaries, navigation, secrets). |
| **[reference/harness-skill-shape.md](reference/harness-skill-shape.md)** | What `execution_mode="harness"` emits and why: operation cards, operations.json schema, manifest differences, the call_web_api-vs-curl decision rule, post-processing patterns, and how to export. |
| **[reference/troubleshooting.md](reference/troubleshooting.md)** | Symptom → cause → fix for harness-mode skill failures (`forbidden`, `login_required` loops, `login_timeout`, truncation, CORS 502, stale catalog). |

---

## Critical rules (don't get these wrong)

- **Never ship transport code in a harness skill.** No `noui_runtime/`, no `httpx`, no Tabby URLs, no token logic. If you find yourself writing a script that calls Tabby, you're building a classic skill, not a harness skill.
- **`call_web_api` is invoked by the agent, not by scripts.** A bash script inside the sandbox cannot reach the tool. Recipes go in SKILL.md; the LLM executes them.
- **The `app` parameter is the Tabby profile** (slug as recorded by NoUI). The profile must be **ACTIVE** and in the harness agent client's **`allowed_profiles`**, or every call returns `forbidden`.
- **`static_secret_header` workflows cannot run in the harness** (gap G1): the sandbox has no env vars and tool-call headers transit the model context. The compiler hard-warns on such exports — keep those skills on the classic/MCP path until server-side secret injection exists.
- **Auth prerequisites are gone, not moved.** Harness-mode SKILL.md must not mention `tabby session ensure`, `TABBY_CLIENT_ID`, or `.env` — first use triggers the built-in `login_required` HITL instead.
- **Respect the text cap.** ~20k chars per result (configurable harness-side). Pagination params in the recipe beat post-hoc truncation. Binary downloads through `call_web_api` are unusable (gap G2).
- **Page origin matters.** `/execute/fetch` runs `fetch()` in the profile's current browser page; a session parked on the wrong origin 502s (gap G3). The profile's login DSL must end on the target site's origin.
- **Skill uploads are org-scoped and override defaults totally.** Slug must match `^[a-z0-9][a-z0-9-]*$`, bundle ≤50 MB; freshly published skills can be invisible to some workers for up to ~30 s (per-process catalog caches, gap G5).

---

## Related

- **/noui-tabby-integration** — the Tabby side of this story: Apps, ServiceProfiles, App Templates, `owner_user_id` scoping, `/execute/fetch` mechanics. The harness's `call_web_api` sits on top of exactly that runtime.
- **/noui-record-workflow** — records the workflow; add `--execution-mode harness` at export time to target the harness.
- **/noui-generalize** — parameter naming/generalization applies to harness recipes the same as classic operations; transport fixes (CDP rewrites) do not.
- Workspace plans: `plans/noui/noui-harness-integration-skill-plan.md` (the strategy this skill implements), `plans/adoptai-workflows/agent-harness-call-web-api-gaps.md` (the G1–G5 platform gap register referenced throughout), `plans/adoptai-workflows/noui-discovery-engine-for-agent-harness-plan.md` (the parent discovery-engine vision).

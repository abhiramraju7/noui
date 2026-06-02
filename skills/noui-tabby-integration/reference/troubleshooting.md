# Troubleshooting: Tabby ↔ NoUI runtime & provisioning failures

Symptom → cause → fix for the common failures. Most "my generated tool doesn't work" issues are one of: (1) profile still STAGING, (2) no live session, (3) `execute_enabled`/worker not mounted, (4) wrong auth mode for cloud, (5) the `credential_types` cookie bug, or (6) a port mismatch. The deeper "why" for each is in [concepts.md](concepts.md), [provisioning.md](provisioning.md), and [execute-and-runtime.md](execute-and-runtime.md).

---

## Provisioning

| Symptom | Likely cause | Fix |
|---|---|---|
| Tool fails `404 No active profile found for "<slug>"` | Profile is still **STAGING**. The login flow (`register/credentials/validate/session ensure`) never promotes; the runtime resolves only ACTIVE/CANARY. | Promote to ACTIVE: run `noui tabby setup` for the profile, or promote via `POST /admin/profiles/{db_id}/promote` (twice, satisfying the canary gate), or the `/noui-generalize` "Fix B" SQL. (`credentials.service.ts:224,268`) |
| `404` even though I see the profile in the DB | The DB row exists but with a non-NULL `owner_user_id` (federated/auto-provisioned), and your token (agent or a *different* user) doesn't match. | An agent token resolves only NULL-owner shared rows; a federated token resolves only its own. Use the matching identity, or create a NULL-owner shared profile / a template. (`credentials.service.ts:228-240`) |
| `POST /admin/profiles` returns `403` | Provisioning token isn't Admin. `/admin/profiles` is `@Roles('Admin')`. | Set `TABBY_ADMIN_TOKEN`, or `ADMIN_BOOTSTRAP_EMAIL/PASSWORD` in `tabby/.env.local` so `_get_admin_token` can log in. (`cli/main.py:639`) |
| token-exchange / `--cloud` fails `401 Tenant not found` | The org's tenant doesn't exist in cloud Tabby. | The tenant (== platform org id) must be created/enabled in cloud first; it is a manual prereq. (`plans/noui/noui-cloud-tabby-auth-plan.md`) |
| Ran `tabby setup --cloud` but no connection exists | Bare `--cloud` only **verifies** the token round-trip; it provisions nothing. | Re-run with `--template-bundle <bundle.json>` to provision a tenant-wide App Template, or run `noui tabby template create <bundle.json>` / `noui login register --as-template` (the gap-closure plan A1/A3). For local, `tabby setup` / `login register`. |

## Live session

| Symptom | Likely cause | Fix |
|---|---|---|
| `404 No healthy session available` | No live worker for the profile's app (never started, idle-shut, or worker died). Execute does **not** auto-rescale. | `noui tabby session ensure --profile <slug>`. Note the runtime only special-cases 409, so 404 may surface opaquely (gap B2). (`credentials.service.ts:363`) |
| `409 Session has no assigned worker pod` | Session row exists but `pod_name` is null (not yet scheduled). | Wait/retry, or re-run `session ensure`. (`execute.service.ts:77`) |
| `409 ... driven by another consumer` (browser only) | Per-session Redis lock held — `/execute/browser` allows one consumer at a time. | Serialize browser calls for that session; retry after the holder releases. (`execute.service.ts:174`) |
| `session ensure` says "✓ HEALTHY" but execute still fails | It probes CDP `:9222`, not the execute server `:8091`; the worker may have no `/execute/*` routes. | Ensure `EXECUTE_ENABLED=true` for the worker (see below); probe `/execute/fetch` directly. (gap B3/B4) |
| Stale "HEALTHY" session that doesn't work | DB says HEALTHY but the local worker PID is dead. | `session ensure` detects this and restarts; if not, `tabby session stop` then `ensure`. (`cli/main.py:4470`) |

## Execute / worker

| Symptom | Likely cause | Fix |
|---|---|---|
| `502 Worker unreachable` locally | `LOCAL_WORKER_URL` unset → API tries the K8s DNS name, which doesn't resolve locally. | Set `LOCAL_WORKER_URL=http://localhost:8091` in the API env. (gap B3) |
| `502` / no execute routes after a clean install | Worker started without `EXECUTE_ENABLED=true` (routes only mount when true), and the app row has `execute_enabled=false`. | Set `EXECUTE_ENABLED=true` in `tabby/.env.local`. NoUI now sets `execute_enabled: true` on new app payloads (the gap-closure plan A4), and `session ensure` warns on a false app row — but a **pre-existing** app or a **per-user auto-provisioned** cloud app may still be false (the Tabby-side template `execute_enabled` copy is pending). Re-provision, or patch the app. (`health-server.ts:33`, `reconcile.service.ts:224`) |
| `429 rate limit` | >60/min (fetch) or >120/min (browser) per profile. | Throttle; the window is 60s, per-profile. |
| `504` on a long call | `timeout_ms` (≤60s) exceeded, or near the worker proxy token's 2-min ceiling. | Keep single calls well under 2 min; chunk long operations; ensure API/worker clock sync. |

## Auth mode (cloud)

| Symptom | Likely cause | Fix |
|---|---|---|
| Cloud-configured tool fails "TABBY_CLIENT_ID and TABBY_CLIENT_SECRET must be set" | Runtime resolved to `agent_token` mode but no agent creds are set — usually `ADOPT_*` aren't all present and `NOUI_TABBY_AUTH_MODE` isn't `platform_jwt`. | The default `tabby` runtime now supports `platform_jwt` (the gap-closure plan A2): set `ADOPT_API_URL`/`ADOPT_CLIENT_ID`/`ADOPT_CLIENT_SECRET` (or `NOUI_TABBY_AUTH_MODE=platform_jwt`), e.g. via `tabby setup --cloud`. No `--execution-mode http` workaround needed. |
| Federated user never gets their own profile | The default `tabby` execute path now carries `owner_user_id` (platform_jwt), but a matching App Template must exist for the slug, and (cloud) the auto-provisioned app needs `execute_enabled`. | Ensure `platform_jwt` mode, provision a template (`tabby template create` / `login register --as-template` / `tabby setup --cloud --template-bundle`), and apply the pending Tabby-side `execute_enabled` change (the gap-closure plan A1/A4). Note: bare `/execute/fetch` does **not** auto-provision — the trigger is `/credentials/request`; ensure the profile is provisioned/warmed first. |

## Credentials content

| Symptom | Likely cause | Fix |
|---|---|---|
| Credentials come back with empty `name`/`value` (cookies) | `credential_types.cookies` was emitted as a **string array**; the Tabby consumer needs `[{name, volatility}]` objects. Recurs on every `register`. | Durable fix: emit object form in `tabby_draft_generator.py` (gap D1). Stopgap: `/noui-generalize` "Fix A" SQL to rewrite the DB row to object form. (`credentials.service.ts:629`) |
| `/credentials/request` returns empty values, no error | No extracted artifact bundle yet, or the API pod is missing `TENANT_ENCRYPTION_KEY`. | Confirm the session actually logged in and extracted; verify `TENANT_ENCRYPTION_KEY` is set on the API. HEALTHY ≠ extracted (gap B6). |
| `/execute/fetch` returns the target's 401/403 inside a 200 body | The session is HEALTHY but not actually authenticated (login DSL incomplete; keepalive passed pre-login on an SPA). | Pre-warm via `session ensure --open <authenticated-url>`; verify a known authenticated request before trusting output. |

## Configuration

| Symptom | Likely cause | Fix |
|---|---|---|
| CLI reaches Tabby but the generated tool can't (or vice-versa) | Port split-brain: CLI/`.env` default `:8080` (legacy), generated runtime defaults `:8000`, Tabby runs on `:8000`. | Set `TABBY_API_URL=http://localhost:8000` explicitly everywhere. (gap D7) |
| `streaming_mode` in `browser_policy` seems ignored | It **is** a no-op in Tabby (VNC is always on for HITL). | Harmless; ignore (or remove from payloads). Tabby gotcha #18. |
| Keepalive flaps / health fails on an SPA | `login register` forces `dom_check` on `body`, which can return false-negative on Salesforce Lightning/Workday; or `url_check` 429s. | Pick a stable authenticated URL for `url_check`, or a specific (non-`body`) `dom_check` selector. (gap D8) |

---

## Fast triage flow

```
Tool fails at runtime
  ├─ 404 "No active profile"     → profile is STAGING → promote (tabby setup / promote / Fix B)
  ├─ 404 "No healthy session"    → no live worker → tabby session ensure --profile <slug>
  ├─ 409 "no worker pod"         → session not scheduled → retry / re-ensure
  ├─ 409 "driven by another"     → /execute/browser lock → serialize calls
  ├─ 502 unreachable             → LOCAL_WORKER_URL unset OR EXECUTE_ENABLED=false (app/worker)
  ├─ "TABBY_CLIENT_ID must be set" (cloud) → mode resolved to agent_token → set ADOPT_* / NOUI_TABBY_AUTH_MODE=platform_jwt (tabby setup --cloud)
  ├─ empty cookies               → credential_types string-array bug → Fix A SQL / fix emit (D1)
  └─ target 401/403 in body      → HEALTHY ≠ authenticated → pre-warm + verify auth
```

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
| Ran `tabby setup --cloud` but no connection exists | `--cloud` only **verifies** the token round-trip; it provisions no App/Profile/Template. | Provision separately (today: local `tabby setup` / `login register`; the cloud template-emitter is unbuilt — see [gaps.md](gaps.md) A1/A3). |

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
| `502` / no execute routes after a clean install | Worker started without `EXECUTE_ENABLED=true` (routes only mount when true), and the app row has `execute_enabled=false`. | Set `EXECUTE_ENABLED=true` in `tabby/.env.local`; for cloud/K8s the **app** must have `execute_enabled: true` (NoUI never sets it — gap A4). (`health-server.ts:33`, `reconcile.service.ts:224`) |
| `429 rate limit` | >60/min (fetch) or >120/min (browser) per profile. | Throttle; the window is 60s, per-profile. |
| `504` on a long call | `timeout_ms` (≤60s) exceeded, or near the worker proxy token's 2-min ceiling. | Keep single calls well under 2 min; chunk long operations; ensure API/worker clock sync. |

## Auth mode (cloud)

| Symptom | Likely cause | Fix |
|---|---|---|
| Cloud-configured tool fails "TABBY_CLIENT_ID and TABBY_CLIENT_SECRET must be set" | Default `tabby` runtime is agent-token-only and ignores `NOUI_TABBY_AUTH_MODE=platform_jwt`. | Export with `--execution-mode http` (honors `platform_jwt`), or also set `TABBY_CLIENT_ID/SECRET`. Root fix: port `platform_jwt` into `execute.py` (gap A2). |
| Federated user never gets their own profile | The path that auto-provisions is `/credentials/request` with an `owner_user_id`-bearing token; the default `tabby` execute path can't trigger it. | Use `http` mode (platform_jwt) so the token carries `owner_user_id`, and ensure a tenant App Template exists for the slug (unbuilt — gap A1). |

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
  ├─ "TABBY_CLIENT_ID must be set" (cloud) → default tabby mode can't do platform_jwt → export --execution-mode http
  ├─ empty cookies               → credential_types string-array bug → Fix A SQL / fix emit (D1)
  └─ target 401/403 in body      → HEALTHY ≠ authenticated → pre-warm + verify auth
```

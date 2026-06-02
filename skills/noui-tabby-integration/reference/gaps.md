# End-to-end gaps in the Tabby ↔ NoUI integration

A prioritized, evidence-backed catalogue of the gaps in the integration, with a focus on the **tenant-wide / scalable provisioning** path. Each gap notes its **side** (NoUI / Tabby / integration / docs), severity, evidence (`path:line`), and a recommendation. No time estimates — see the sequencing notes at the end.

Many of these are already partially tracked in `plans/noui/noui-agent-friction-retro-plan.md` (the 17-item friction backlog) and `plans/noui/noui-cloud-tabby-auth-plan.md`. This doc focuses on the App/Profile/Template provisioning and execute paths specifically.

---

## A. The tenant-wide provisioning gap (the critical path)

These four together are why a connection is "creator-only" and does not scale, and exactly what blocks the decided "emit App Templates" intent.

### A1 — NoUI never emits App Templates `[critical · NoUI]`
The entire template-based, tenant-wide provisioning primitive is unwired on the NoUI side. NoUI hand-rolls raw `POST /apps` + `POST /admin/profiles` per profile and manually walks `STAGING→CANARY→ACTIVE`; it never creates a template.
- **Evidence:** grep across `cli/ backend/ runtime/ compiler/` for `app-template|profile_name_pattern|autoProvisionFromTemplate` → empty. `cli/main.py:1067,1083,3782,3825`. Tabby has the full feature idle: `tabby/.../app-templates/app-templates.controller.ts`, `credentials.service.ts:280` (`autoProvisionFromTemplate`).
- **Recommendation:** build a template emitter (`POST /admin/app-templates`) deriving template fields from the existing `application_draft`+`service_profile_draft`; `profile_name_pattern` **must** equal the runtime `PROFILE_SLUG`. Keep the raw path only for local single-dev (agent-token) mode. This is the deferred "Caveat 3" follow-on in `plans/noui/noui-cloud-tabby-auth-plan.md`.

### A2 — Default `tabby` runtime is agent-token-only, so it can never trigger auto-provisioning `[critical · NoUI]`
Even if a template existed, the default execution path can't use it. `execute_adapter.py` only does `_get_agent_token()` (agent token → no `owner_user_id`), and `autoProvisionFromTemplate` is gated on `if (ownerUserId)`. With a null owner, `resolveActiveProfile` matches only NULL-owner shared rows and `404`s rather than provisioning.
- **Evidence:** `compiler/runtime/execute_adapter.py:93-116` (no `platform_jwt`/`ADOPT_`/`NOUI_TABBY_AUTH_MODE`); `tabby/.../auth.service.ts:183` (agent JWT has no owner); `credentials.service.ts:244` (`if (ownerUserId)` gate), `:236-240` (NULL-only fallback).
- **Recommendation:** port the `platform_jwt` two-step (already in `auth_adapter.py:154-202`) into `execute_adapter.py`, with per-mode bearer caching. Without this the cloud sharing story is dead on arrival for the default mode.

### A3 — `tabby setup --cloud` provisions nothing and is incompatible with the default runtime `[critical · NoUI]`
A double dead-end: (1) `--cloud` only verifies the token round-trip and writes env — no `/apps`, `/admin/profiles`, or `/admin/app-templates` call; (2) it writes `NOUI_TABBY_AUTH_MODE=platform_jwt`, which the default `tabby` runtime never reads (it requires `TABBY_CLIENT_ID/SECRET`).
- **Evidence:** `cli/main.py:4086-4166` (no provisioning call); `execute_adapter.py:100-116` (agent-token only).
- **Recommendation:** have `--cloud` emit/upsert an App Template after verifying the round-trip (pairs with A1), and fix the runtime to honor `platform_jwt` (pairs with A2). Until both land, document that `--cloud` is auth-verification-only and the default `tabby` export has no working cloud auth.

### A4 — `execute_enabled` is never set → defaults `false` `[high · NoUI + Tabby]`
NoUI sets `execute_enabled` nowhere; `autoProvisionFromTemplate` doesn't set it; the template entity has no field for it. In K8s the worker Service and pod `EXECUTE_ENABLED` are gated on it, so `/execute/fetch` `502`s. Works locally only via the `.env.local` `EXECUTE_ENABLED=true` override + `LOCAL_WORKER_URL`.
- **Evidence:** grep `execute_enabled` in `cli/ compiler/ backend/` → empty; `tabby/.../application.entity.ts:60` (default false, migration 022); `apps/controller/src/reconcile.service.ts:224`, `pod-manager.service.ts:365`; `credentials.service.ts:299-311` (auto-provision omits it).
- **Recommendation:** set `execute_enabled: true` in the compiler's `application_draft`, `tabby setup`'s `_build_app_payload`, and the template emitter; add `execute_enabled` to `AppTemplateEntity` + `autoProvisionFromTemplate` (Tabby change); add a `session ensure` warning if the app row has it false.

---

## B. Runtime reliability & session lifecycle

### B1 — Login flow leaves the profile in `STAGING`, but the runtime needs `ACTIVE`/`CANARY` `[critical · docs/NoUI]`
The documented `/noui-record-login` happy path (`register → credentials → validate → session ensure`) never promotes. `/execute/fetch` and `/credentials/request` resolve only `ACTIVE`/`CANARY` → `404 No active profile`. Only `tabby setup` (or a manual promote) advances it.
- **Evidence:** `cli/main.py:1097` (STAGING), `:1130-1207` (validate polls *session* state only); `credentials.service.ts:224,268`.
- **Recommendation:** add an explicit promote step to the login path (or document that it stops at STAGING and won't resolve until promoted). Make `/noui-generalize` "Fix B" the standard promotion step, not an edge case.
- **Status — implemented (NoUI + docs).** The promote sequence (two `POST /admin/profiles/{id}/promote` calls bracketing the `_bypass_canary_gate` Postgres `UPDATE`) was extracted from `_ensure_service_profile` into a reusable `_promote_profile_to_active(profile_db_id, admin_token)` helper. Three affordances now expose it: (1) `noui login register <bundle> --promote` promotes inline and records `version_state: ACTIVE`; (2) a new `noui login promote <bundle>` command promotes a previously-registered profile (no-op if already ACTIVE); (3) `noui login import <session_id> --promote` threads the flag through the convenience wrapper. Plain `register` still stops at STAGING but now prints a `noui login promote` follow-up hint. The `/noui-record-login` skill doc gains a "STAGING trap" warning, a Step 6b, the flow-diagram step, and the new commands in the reference table. Tests: `tests/test_cli_tabby.py::TestPromoteProfileToActive`, `::TestLoginPromoteCommand`, `::TestLoginRegisterPromoteFlag`.

### B2 — `/execute/*` returns `404` for "no healthy session", but the runtime only special-cases `409` `[high · integration]`
`findHealthySession` throws `404`; the runtime's `execute_fetch` only maps `409` to the actionable "run `tabby session ensure`" message, so the common no-session case surfaces as an opaque `404`.
- **Evidence:** `credentials.service.ts:362-363` (404); `execute_adapter.py:168-177` (only 409 special-cased).
- **Recommendation:** treat `404 No healthy session` like `409` in `execute_adapter.py` — raise the "run `tabby session ensure --profile <slug>`" error.
- **Status — implemented (NoUI).** `execute_adapter.py` now routes both `409` and `404`-with-a-session-marker (`"no healthy session"` / `"no active profile"` in the body) through a shared `_is_no_session()` helper to the actionable "run `tabby session ensure --profile <slug>`" error. A bare `404` without the marker, and an upstream `404` wrapped in a `200 {status:404}` body, are deliberately *not* misclassified. Tests: `tests/test_execute_adapter.py::TestNoSessionErrors`.

### B3 — Fresh local installs silently can't run `/execute/fetch` (`EXECUTE_ENABLED`/`LOCAL_WORKER_URL` not guaranteed) `[high · NoUI/Tabby]`
The worker only mounts `/execute/*` if `EXECUTE_ENABLED==='true'`; the API needs `LOCAL_WORKER_URL` in dev (the K8s DNS name is unresolvable locally). `session ensure` doesn't inject either; `tabby/.env.example` lacks both. A new dev gets a worker with no execute routes and the failure only appears at first tool call.
- **Evidence:** `apps/worker/src/health-server.ts:33`; `execute.service.ts` (LOCAL_WORKER_URL else K8s DNS); `cli/main.py:4488-4497` (no EXECUTE_ENABLED/LOCAL_WORKER_URL); `tabby/.env.example` (missing both).
- **Recommendation:** inject `EXECUTE_ENABLED=true` into the spawned worker and assert/inject `LOCAL_WORKER_URL`; add both to `tabby/.env.example`; add an execute-readiness probe to `session ensure`.
- **Status — NoUI-done + Tabby-documented.** `cmd_session_ensure` now forces `EXECUTE_ENABLED=true` into the spawned worker's subprocess env (so `/execute/*` is always mounted) and seeds `LOCAL_WORKER_URL=http://localhost:8091` into that env. Because the *API* (not this worker) is the process that reads `LOCAL_WORKER_URL` and it was started separately by `noui tabby start`, `session ensure` cannot set it on the live API process — so it warns loudly when `LOCAL_WORKER_URL` is absent from both `os.environ` and `tabby/.env.local`, pointing the user to add it and restart. Paired with the B4 readiness probe.
  - **Tabby half (document-only, needs submodule PR):** add to `tabby/.env.example` (pinned submodule — do not edit from this branch):
    ```
    # Enables the worker's /execute/* HTTP routes (health-server.ts gate).
    EXECUTE_ENABLED=true
    # Dev-only: where the API reaches the per-session worker. In K8s this is the
    # service DNS name; locally that name is unresolvable so set it explicitly.
    LOCAL_WORKER_URL=http://localhost:8091
    ```

### B4 — `session ensure` reports HEALTHY by probing CDP `:9222`, not the execute server `:8091` `[high · NoUI]`
The readiness check validates the wrong surface — a session can be "✓ HEALTHY" with no `/execute/fetch` route mounted.
- **Evidence:** `cli/main.py:4468-4479` (state + PID + `_cdp_is_reachable` on `:9222`); `health-server.ts:33` (execute routes independent of CDP).
- **Recommendation:** after HEALTHY, probe a trivial `/execute/fetch` (or the worker `:8091`) and distinguish ":9222 CDP" from ":8091 execute" in status output.
- **Status — implemented (NoUI).** Added `_probe_execute_ready(profile_id, admin_token)` — a trivial `POST /execute/fetch` (to `https://example.com/`, 5 s) classified into `ready` / `no-route` (404 marker, bare 404 ⇒ routes not mounted, 502/504 ⇒ worker unreachable) / `unknown` (probe itself couldn't run). `_report_execute_readiness` prints separate `CDP :9222` and `Execute :8091` status lines and warns when execute is not ready. Both `session ensure` success paths (already-HEALTHY early return and the fresh-start path) call it. The probe never raises — a probe failure degrades to a warning and never crashes `session ensure` (guardrail). Tests: `tests/test_cli_tabby.py::TestProbeExecuteReady`, `::TestReportExecuteReadiness`.

### B5 — `/execute/*` doesn't rescale idle-shutdown apps or refresh the idle timer `[medium · integration]`
`/credentials/request` rescales an idle app to 1 on "no healthy session" and updates `last_credential_request_at`; `/execute/*` does neither. An execute-only tool never refreshes the idle timer → the app idle-shuts → next call `404`s with no auto-recovery.
- **Evidence:** `credentials.service.ts:130-141,144` vs `execute.service.ts:69-79`.
- **Recommendation:** mirror the rescale-on-404 logic in execute (Tabby), and/or on the NoUI side fall back to one `/credentials/request` to warm the session, then retry execute.
- **Status — NoUI-done + Tabby-documented.** NoUI half: `execute_adapter.py` now supports an **opt-in** one-shot warm-up. Set `NOUI_EXECUTE_WARMUP=1` and, on a no-session 404/409, the runtime issues exactly one `POST /credentials/request` (which rescales an idle-shut app to 1 and triggers `autoProvisionFromTemplate`) then retries `/execute/fetch` **once** — no loops. A failed warm-up (5xx, or any transport error) does not retry and never masks the actionable B2 error. Off by default so the common path keeps its single-request latency. Tests: `tests/test_execute_adapter.py::TestWarmUpRetry`.
  - **Tabby half (document-only, needs submodule PR):** mirror the rescale-on-no-healthy-session logic from `apps/api/src/credentials/credentials.service.ts` (the rescale-to-1 + `last_credential_request_at` update at ~`:130-141,144`) into `apps/api/src/execute/execute.service.ts` `executeFetch` (~`:69-79`), so `/execute/*` itself refreshes the idle timer and recovers an idle-shut app without needing the NoUI-side warm-up. This is the durable fix; the NoUI warm-up is the client-side stopgap.

### B6 — `HEALTHY` ≠ authenticated/extracted `[medium · integration]`
HEALTHY only means the keepalive passed. A missing artifact bundle yields **silently empty** credentials on the credentials path; on the execute path an unfinished login lets `fetch(credentials:'include')` run unauthenticated and return the target's 401/403 as a 200-wrapped body.
- **Evidence:** `credentials.service.ts:178-192` (null bundle → empty, no throw); `execute-handler.ts:60` (live-jar dependency); Tabby gotchas #9/#10/#16.
- **Recommendation:** document HEALTHY≠authenticated; pre-warm with `session ensure --open <auth-url>` and verify a known authenticated request before trusting output.
- **Status — docs-only (implemented).** Concise "HEALTHY ≠ authenticated" warnings added to `/noui-record-login` (Step 9, after the session-ensure output) and `/noui-record-workflow` (prerequisite block): both explain the 401/403-wrapped-as-200 failure, instruct to pre-warm with `tabby session ensure --profile <slug> --open <auth-url>` (or `--skill <id>`), and to verify one known-authenticated request before trusting output. The deeper detail already lives in `/noui-tabby-integration` (concepts/execute-and-runtime). No code change (per the gap's recommendation).

### B7 — `findHealthySession` is non-deterministic with duplicate HEALTHY rows `[medium · Tabby]`
`findOne(... HEALTHY ...)` has no `ORDER BY`; if reconciliation left two HEALTHY rows, the chosen `pod_name` is arbitrary and may point at a gone pod → `502`.
- **Evidence:** `credentials.service.ts:347-361` (no order).
- **Recommendation:** add `ORDER BY updated_at DESC`, prefer a non-null recently-heartbeated `pod_name`.
- **Status — document-only (Tabby submodule; needs a separate Tabby PR).** Verified against the live submodule: `apps/api/src/modules/credentials/credentials.service.ts` `findHealthySession` (≈`:347-366`) builds `where = { tenant_id, state: 'HEALTHY', app_id?, owner_user_id? }` and calls `this.sessionRepo.findOne({ where })` with **no `order`** — so with duplicate HEALTHY rows (a reconciliation race) the returned row, and thus `pod_name`, is arbitrary and can point at a terminated pod → `502` on execute/credentials. **Required change (Tabby-side, do NOT edit from this branch):** pass an ordering to `findOne`, preferring the freshest heartbeat and a live worker, e.g.:
  ```ts
  const session = await this.sessionRepo.findOne({
    where,
    order: { updated_at: 'DESC' },   // newest heartbeat first
  });
  ```
  Ideally also bias toward a non-null `pod_name` (e.g. a query-builder `ORDER BY pod_name IS NULL ASC, updated_at DESC`) so a row with an assigned worker wins over a pod-less one. No NoUI-side half — this is purely a Tabby resolver determinism fix. The NoUI B5 warm-up retry mitigates the *symptom* (a stale-pod 502/404 can be retried after a warm-up) but does not fix the non-determinism.

---

## C. Security & tenant-isolation findings (Tabby-side — confirm with the Tabby team)

These are adversarial gap-analysis findings with code citations. They are **Tabby-side** and high-impact; validate them with the Tabby team before relying on (or documenting as guaranteed) tenant isolation. They also bound how safely a tenant-wide template path can be shipped.

### C1 — Cross-tenant K8s login-secret mount via unscoped `credential_ref` `[critical · Tabby]`
`credential_ref` is validated only for the `k8s:secret/` prefix; the secret **name** is arbitrary and mounted verbatim from a single shared worker namespace, with no tenant prefix or allowlist. Since any authenticated user can create an app/template in their tenant, a user could set `credential_ref: k8s:secret/<other-tenant-secret>` and the worker would mount it.
- **Evidence:** `packages/shared/src/dsl.validator.ts:185`; `apps/controller/src/pod-manager.service.ts:461,336,23`.
- **Recommendation:** namespace the mounted secret by tenant (`${tenantId}-${ref}` or per-tenant namespaces); reject refs to non-tenant-owned secrets at create time; audit every mount.

### C2 — Single global `TENANT_ENCRYPTION_KEY` — no cryptographic tenant isolation `[critical · Tabby]`
Extracted-credential bundles are AES-256-GCM encrypted/decrypted with one global key injected into every worker pod. MinIO buckets are path-isolated per tenant, but the cipher key is universal — cross-tenant confidentiality rests entirely on bucket/DB scoping. (Note: several docs/plans claim a "per-tenant encryption key" — that is **false** per the code.)
- **Evidence:** `apps/worker/src/artifact-extractor.ts:423`; `credentials.service.ts:469`; `pod-manager.service.ts:362`; `minio-provisioner.service.ts:38`.
- **Recommendation:** derive a per-tenant key (HKDF(master, tenant_id) or KMS), store key id/version on `artifact_bundles`. Correct the "per-tenant key" claim wherever it appears.

### C3 — No real audit trail on credential issuance `[high · Tabby]`
`POST /credentials/request` returns decrypted live credentials but writes no hash-chained audit event; the only record (`artifact_consumptions.consumer_id`) is a **random per-request UUID**, not the calling user/agent. You cannot answer "who used this connection" — which matters most for shared (NULL-owner) connections.
- **Evidence:** `credentials.controller.ts:64` (random `requestId`); `credentials.module.ts` (no `AuditModule`); `credentials.service.ts:451-462`.
- **Recommendation:** log an `AuditService` event with real `actor_id`/`owner_user_id`/`profile_id`/`session_id`; populate `consumer_id` with the caller identity.

### C4 — `agent_assertion` mints a federated token for any `target_user_id` with no membership check `[high · Tabby]`
Any holder of a valid agent JWT can mint an owner-scoped token for an arbitrary `target_user_id` (only checks: agent token present, `token_type==='agent'`, non-empty target) and then read that "user's" credentials / drive their session — a broad impersonation primitive.
- **Evidence:** `token-exchange.service.ts:234-273` (3 guards, `owner_user_id = target_user_id` verbatim, role defaults Operator).
- **Recommendation:** validate `target_user_id` against tenant users / an impersonation allowlist; don't silently default the role.

### C5 — Worker execute tenant-check is fail-open `[high · Tabby]`
The worker accepts the proxy token if signed; it only enforces the tenant match **when the token carries `tenant_id`** (`if (payload.tenant_id && payload.tenant_id !== TENANT_ID)`). A signed token without `tenant_id` passes on any worker — fail-open.
- **Evidence:** `apps/worker/src/execute-auth.ts:21`.
- **Recommendation:** fail-closed (`if (payload.tenant_id !== TENANT_ID) 403`), require `token_type==='service'` + short exp; consider per-tenant signing keys.

### C6 — `GET /sessions/:id` is tenant-only, not owner-scoped `[high · Tabby]`
List is owner-scoped, but the detail and interventions endpoints filter only by `tenant_id` — any Operator/Viewer/Agent can read another user's per-user session by UUID, contradicting the per-user isolation guarantee.
- **Evidence:** `sessions.controller.ts:60-68`, `sessions.service.ts:88-95` (no owner filter); contrast `sessions.controller.ts:56` (list is scoped).
- **Recommendation:** apply the same owner-scoping to `findOne`/`findInterventions`.

### C7 — `POST /admin/app-templates` has no `@Roles` — any authenticated user can create the auto-provisioning blueprint `[medium · Tabby]`
A low-privilege user can plant a template whose `profile_name_pattern` any future user instantiates, with attacker-chosen `target_domains`, harvested `credential_types`, and `credential_ref` (ties to C1). `PUT`/`DELETE` are Admin-only, but `POST`/`GET` are not.
- **Evidence:** `app-templates.controller.ts:59-77` (no `@Roles` on POST/GET); `common/guards/roles.guard.ts:18` (no roles ⇒ allow).
- **Recommendation:** require `@Roles('Admin')` (or a template-management role) on `POST`; validate `credential_ref`/`target_domains` at create time.

### C8 — Shared (NULL-owner) connection = one logged-in identity for the whole tenant `[high · integration]`
This is the default posture of NoUI's direct + agent-token path. Every Operator/Agent with a token for that `profile_id` acts as one logged-in identity on the target SaaS, with no per-user attribution (C3), and one CAPTCHA/MFA/lockout takes out the tenant. VNC owner-gating also degrades (no single owner).
- **Recommendation:** gate sharing behind an explicit opt-in; push multi-user to the federated/template (owner-scoped) path; pair with the audit fix (C3).

### C9 — Template edits don't propagate to already-provisioned per-user profiles `[high · Tabby]`
`propagateToLinkedApps` updates only **applications** (5 fields), never the cloned per-user `service_profiles`. A security-tightening edit to `credential_types`/`login_config` reaches **zero** already-provisioned users.
- **Evidence:** `app-templates.service.ts:84-117` (appRepo only); `credentials.service.ts:321-330` (profile snapshots template config at provision).
- **Recommendation:** propagate to linked profiles (or mark stale + re-provision); version provisioned profiles against the template.

### C10 — Federated tokens aren't revocation-checked when `jti` is null `[medium · Tabby]`; auto-provisioned profiles skip the canary gate `[low · Tabby]`
Externally-validated IdP tokens (`jti:null`) bypass the blacklist; a leaked owner-scoped token is valid for its full TTL with no kill switch. Separately, auto-provisioned profiles go straight to ACTIVE, removing the canary validation on the attacker-influenceable path.
- **Evidence:** `jwt.strategy.ts:118,123-125`; `credentials.service.ts:327-330`.

---

## D. Documentation / DX corrections (fix in the existing skills)

> **Status — addressed.** D1, D3, D4, D5, D6, D7 and the NoUI-side of D8 (`streaming_mode` removal) are now fixed in code and/or docs; D2 was already resolved during the `cdp`→`tabby` rename. D1 and D7 were fixed at the source (durable), not band-aided: NoUI now emits `credential_types.cookies` as `[{name, volatility}]` objects, and the CLI/backend/verifier default `TABBY_API_URL` is aligned to `:8000`. **Still open (Tabby-side):** D8's dead `AppTemplatesService.findByPattern` and the inert `credential_ref_default` / `idle_shutdown_seconds` template fields — these live in the pinned Tabby submodule and need a separate Tabby change.

### D1 — `credential_types` cookie-shape bug is a NoUI emit bug, not a Tabby bug `[high · docs]`
`/noui-generalize` "Fix A" frames it as a Tabby format bug fixed by one-off SQL. Root cause: NoUI emits a **string array** of cookie names; Tabby's cookie consumer requires `[{name, volatility}]` objects and stores the DTO verbatim. The SQL is a per-profile band-aid that recurs on every `register` and would multiply across all tenant users under a template.
- **Evidence:** `compiler/login/tabby_draft_generator.py:543,201`; `compiler/mcp/auth_plan.py:159`; `credentials.service.ts:629` (cookies strict), `:660` (headers tolerant), `:322` (template reuse).
- **Recommendation:** fix the emit side to object form (durable fix per the workspace "full fixes only" standard); document the cookies-strict/headers-tolerant asymmetry.

### D2 — `/execute/browser` is documented as "future/unavailable" but is live `[high · docs]`
`/noui-generalize` points at a `localhost:9222` CDP-WebSocket workaround. `/execute/browser` (15 commands, per-session lock) is shipped and `execute_browser()` exists; `/noui-autopilot` already uses it.
- **Evidence:** `tabby/.../execute.controller.ts:102`; `skills/noui-autopilot/SKILL.md:23`; `skills/expedia-stay-search/noui_runtime/execute.py:142`.
- **Recommendation:** rewrite those sections to use `execute_browser(...)`; demote the 9222 path to a legacy footnote.

### D3 — Skills point runtime auth at `noui_runtime/auth.py`, but the default mode uses `execute.py` `[high · docs]`
`/noui-generalize` ("both runtimes share `auth.py`") and `/noui-record-login` ("the runtime auth adapter `auth.py`…") are wrong for the default `tabby` mode, which uses `execute.py`/`execute_fetch`. `auth.py` is only the `--execution-mode http` path.
- **Evidence:** `skills/noui-generalize/SKILL.md:24`, `skills/noui-record-login/SKILL.md:179`; `skills/expedia-stay-search/operations/search_hotels.py:30` (imports `execute.py`).

### D4 — Profile `version_state` vs Session `HEALTHY` are conflated `[high · docs]`
`/noui-record-login` says "wait for the profile to reach HEALTHY state" — profiles have no HEALTHY state (`STAGING/CANARY/ACTIVE/RETIRED`); HEALTHY is a Session state, and `login validate` polls the *sessions* table.
- **Evidence:** `skills/noui-record-login/SKILL.md:23,165,279`; `cli/main.py:1172`; `packages/shared/src/enums.ts:5`.

### D5 — Owner-scoping / creator-only semantics are entirely undocumented `[medium · docs]`
No skill mentions `owner_user_id` (grep → 0 hits) or the agent-token-vs-federated reach asymmetry — the very thing that makes a profile creator-only. This skill ([concepts.md](concepts.md)) closes that.

### D6 — Cloud auth + default-mode incompatibility undocumented `[high · docs]`
`/noui-setup` presents `platform_jwt`/`--cloud` as a first-class runtime auth path and claims "the runtime authenticates the same way" — false for the default `tabby` output (see A2/A3). Add the auth-mode × execution-mode matrix (in [execute-and-runtime.md](execute-and-runtime.md)).

### D7 — Port default split-brain `[medium · docs/NoUI]`
CLI/`.env` default `TABBY_API_URL=http://localhost:8080` (legacy), generated runtime defaults to `:8000`, Tabby runs on `:8000`. Align on `8000`; until the code is fixed, always set `TABBY_API_URL` explicitly.
- **Evidence:** `cli/env.py`, `.env.example`, `execute_adapter.py:90`, `tabby/CLAUDE.md:47`.

### D8 — Minor `[low]`
`browser_policy.streaming_mode='cdp'` is sent by both emit sites but ignored by Tabby (gotcha #18); `dom_check` on `body` is forced by `login register` yet can false-negative on SPAs (Salesforce Lightning/Workday) while Tabby guidance prefers `url_check` — document the trade-off; `AppTemplatesService.findByPattern` is dead code and `credential_ref_default`/`idle_shutdown_seconds` template fields are inert.

---

## Sequencing notes (no time estimates)

- **Critical path for tenant-wide provisioning:** A2 (port `platform_jwt` into `execute.py`) and A1 (template emitter) are mutually reinforcing and gate everything else; A4 (`execute_enabled`) and D1 (`credential_types` shape) must land *with* A1 or every auto-provisioned user is broken. A3 is the user-facing wrapper once A1/A2 exist.
- **Risk concentration:** the security cluster (C1, C2, C5, C7) bounds how safely the tenant-wide path can ship — resolve or explicitly accept these before opening template creation to non-admins, since the template is the auto-provisioning blueprint.
- **Quick, independent wins:** B2 (404→actionable error), D2/D3/D4/D6/D7 (doc corrections), B4 (execute-readiness probe) — touch different files, no shared state, can land in parallel and give early signal.
- **Tabby-owned vs NoUI-owned:** A1/A2/A3/A4(NoUI half)/B4/D1/D7 are NoUI-side; A4(template half)/B5/B7/C* are Tabby-side and need coordination with the Tabby team.
- **Lands last:** the end-to-end cloud proof (hop 3 — a federated `/credentials/request` that actually auto-provisions from a NoUI-emitted template) can only be validated after A1+A2+A4 are in place; it has never succeeded end-to-end per `plans/noui/noui-cloud-tabby-auth-plan.md`.

# End-to-end gaps in the Tabby ↔ NoUI integration

A prioritized, evidence-backed catalogue of the gaps found in the integration, focused on the **tenant-wide / scalable provisioning** path. Each gap notes its **side** (NoUI / Tabby / integration / docs), severity, evidence (`path:line`), and status.

> **Scope.** This doc now tracks the **NoUI-side** gaps — most of which are resolved on `feat/noui-tabby-integration`. All **Tabby-side** work — the security findings (the former Topic C) and the Tabby halves of A4/B3/B5/B7 plus the D8 cruft — has moved to a dedicated, verified plan: **`plans/tabby/tabby-noui-integration-hardening-plan.md`** (in the adopt workspace). Items below point there for their Tabby half. Related NoUI plans: `plans/noui/noui-cloud-tabby-auth-plan.md`, `plans/noui/noui-agent-friction-retro-plan.md`.

---

## A. The tenant-wide provisioning gap (the critical path)

These four together are why a connection is "creator-only" and does not scale, and exactly what blocks the decided "emit App Templates" intent.

### A1 — NoUI never emits App Templates `[critical · NoUI]`
**Status: IMPLEMENTED (NoUI). Live cloud-Tabby validation pending.** Added a pure payload builder `build_app_template_payload(application_draft, service_profile_draft)` in `compiler/login/tabby_draft_generator.py` and a CLI emitter `_emit_app_template` + `noui tabby template create [--upsert]` (POST/PUT `/admin/app-templates`) in `cli/main.py`, plus a `noui login register --as-template` affordance that emits the template alongside the raw App+Profile (upsert). The builder forces `profile_name_pattern == service_profile_draft.profile_id` (the runtime `PROFILE_SLUG`) so `autoProvisionFromTemplate` matches, folds the profile draft's `credential_types`/`target_domains` into `export_policy` (where `autoProvisionFromTemplate` reads them at `credentials.service.ts:322-323`), and sets `execute_enabled: true` (A4). The raw `login register`/`tabby setup` single-dev path is unchanged. Unit-tested for payload shape, slug==pattern, credential-type folding, and the POST/PUT/upsert CLI flow. **Cannot be integration-tested end-to-end without a live cloud Tabby** (needs a federated `platform_jwt` request that triggers `autoProvisionFromTemplate`) — the "hop 3" cloud proof.

> ⚠️ **Tabby blocker (see the hardening plan → A4-tabby):** Tabby's `CreateAppTemplateDto` has no `execute_enabled` field and the API runs `forbidNonWhitelisted`, so the template create **400s** on NoUI's payload until the Tabby DTO is updated. The emitter works at the unit level but the cloud round-trip depends on that Tabby change.

### A2 — Default `tabby` runtime is agent-token-only, so it can never trigger auto-provisioning `[critical · NoUI]`
**Status: IMPLEMENTED (NoUI).** `execute_adapter.py` now resolves the auth mode (`_resolve_auth_mode`: explicit `NOUI_TABBY_AUTH_MODE`, else auto-detect `platform_jwt` from `ADOPT_*`, else `agent_token`) and obtains a federated Tabby JWT carrying `owner_user_id` via the two-step exchange (`_get_platform_jwt` → `_get_platform_tabby_token`) when in `platform_jwt` mode, with per-mode bearer caching (`_get_tabby_bearer`). `agent_token` remains the working default. The generated `noui_runtime/execute.py` is regenerated accordingly. Tabby-side `autoProvisionFromTemplate` is now reachable once a template exists (A1) and `execute_enabled` is set (A4).

### A3 — `tabby setup --cloud` provisions nothing and is incompatible with the default runtime `[critical · NoUI]`
**Status: IMPLEMENTED (NoUI). Live cloud-Tabby validation pending.** Both dead-ends are closed: (2) the default `tabby` runtime now honors `platform_jwt` (A2), so the `NOUI_TABBY_AUTH_MODE=platform_jwt` that `--cloud` writes is actually consumed; (1) `tabby setup --cloud --template-bundle <bundle.json>` now provisions a tenant-wide App Template after the round-trip verification, via `_provision_cloud_template`. It reuses `build_app_template_payload` (A1) and POSTs `/admin/app-templates` against the absolute cloud `tabby_url` with the **exchanged Tabby JWT** (POST is open to any authenticated user, so no Tabby admin token is needed). A name-collision `409` is treated as "already exists". With no `--template-bundle`, `--cloud` stays auth-verification-only and prints a hint pointing at `--template-bundle` / `noui tabby template create`. Unit-tested. **End-to-end validation needs a live cloud Tabby** (the auto-provision trigger is a subsequent federated `/credentials`/`/execute` request).

### A4 — `execute_enabled` is never set → defaults `false` `[high · NoUI + Tabby]`
**Status: NoUI DONE; Tabby half → hardening plan.** NoUI now sets `execute_enabled: true` in all three emit sites — the compiler's `application_draft` (`compiler/login/tabby_draft_generator.py`), `tabby setup`'s `_build_app_payload` (`cli/main.py`), and the A1 template emitter payload (`build_app_template_payload`). `noui tabby session ensure` calls `_warn_if_execute_disabled(app_id, admin_token)` and prints a non-fatal warning if the resolved app row has `execute_enabled=false`. Unit-tested.

> **Tabby half → `plans/tabby/tabby-noui-integration-hardening-plan.md` (A4-tabby):** add `execute_enabled` to the App-Template entity (+ migration) and `CreateAppTemplateDto`, and copy it into the `appsService.create(...)` inside `autoProvisionFromTemplate`. ⚠️ Because of `forbidNonWhitelisted`, the DTO field is a **prerequisite** for NoUI's template payload to be accepted at all (not just for execute-enablement).

---

## B. Runtime reliability & session lifecycle

### B1 — Login flow leaves the profile in `STAGING`, but the runtime needs `ACTIVE`/`CANARY` `[critical · docs/NoUI]`
**Status: implemented (NoUI + docs).** The promote sequence (two `POST /admin/profiles/{id}/promote` calls bracketing the `_bypass_canary_gate` Postgres `UPDATE`) was extracted from `_ensure_service_profile` into a reusable `_promote_profile_to_active(profile_db_id, admin_token)` helper. Three affordances expose it: (1) `noui login register <bundle> --promote` promotes inline; (2) a new `noui login promote <bundle>` command (no-op if already ACTIVE); (3) `noui login import <session_id> --promote`. Plain `register` still stops at STAGING but prints a `noui login promote` follow-up hint. `/noui-record-login` gained a "STAGING trap" warning, a Step 6b, the flow-diagram step, and reference-table rows. Tests: `tests/test_cli_tabby.py::TestPromoteProfileToActive`, `::TestLoginPromoteCommand`, `::TestLoginRegisterPromoteFlag`.

### B2 — `/execute/*` returns `404` for "no healthy session", but the runtime only special-cased `409` `[high · integration]`
**Status: implemented (NoUI).** `execute_adapter.py` now routes both `409` and `404`-with-a-session-marker (`"no healthy session"` / `"no active profile"` in the body) through a shared `_is_no_session()` helper to the actionable "run `tabby session ensure --profile <slug>`" error. A bare `404` without the marker, and an upstream `404` wrapped in a `200 {status:404}` body, are deliberately *not* misclassified. Tests: `tests/test_execute_adapter_behaviour.py::TestNoSessionErrors`.

### B3 — Fresh local installs silently can't run `/execute/fetch` (`EXECUTE_ENABLED`/`LOCAL_WORKER_URL`) `[high · NoUI/Tabby]`
**Status: NoUI DONE; Tabby half → hardening plan.** `cmd_session_ensure` now forces `EXECUTE_ENABLED=true` into the spawned worker's subprocess env (so `/execute/*` is always mounted) and seeds `LOCAL_WORKER_URL=http://localhost:8091` into that env. Because the *API* (started separately) is what reads `LOCAL_WORKER_URL`, `session ensure` warns loudly when it's absent from both `os.environ` and `tabby/.env.local`. Paired with the B4 readiness probe.

> **Tabby half → `plans/tabby/tabby-noui-integration-hardening-plan.md` (B3-tabby):** add `EXECUTE_ENABLED=true` and `LOCAL_WORKER_URL=http://localhost:8091` to `tabby/.env.example`.

### B4 — `session ensure` reported HEALTHY by probing CDP `:9222`, not the execute server `:8091` `[high · NoUI]`
**Status: implemented (NoUI).** Added `_probe_execute_ready(profile_id, admin_token)` — a trivial `POST /execute/fetch` classified into `ready` / `no-route` (404 marker / bare 404 ⇒ routes not mounted, 502/504 ⇒ worker unreachable) / `unknown`. `_report_execute_readiness` prints separate `CDP :9222` and `Execute :8091` status lines and warns when execute isn't ready. Both `session ensure` success paths call it; the probe never raises (degrades to a warning). Tests: `tests/test_cli_tabby.py::TestProbeExecuteReady`, `::TestReportExecuteReadiness`.

### B5 — `/execute/*` doesn't rescale idle-shutdown apps or refresh the idle timer `[medium · integration]`
**Status: NoUI DONE (opt-in); Tabby half → hardening plan.** NoUI half: `execute_adapter.py` supports an **opt-in** one-shot warm-up. Set `NOUI_EXECUTE_WARMUP=1` and, on a no-session 404/409, the runtime issues exactly one `POST /credentials/request` (which rescales an idle-shut app and triggers `autoProvisionFromTemplate`) then retries `/execute/fetch` **once** — no loops. A failed warm-up never masks the actionable B2 error. Off by default. Tests: `tests/test_execute_adapter_behaviour.py::TestWarmUpRetry`.

> **Tabby half → `plans/tabby/tabby-noui-integration-hardening-plan.md` (B5-tabby):** mirror the rescale-on-no-healthy-session logic + `last_credential_request_at` refresh from `credentials.service.ts` into `execute.service.ts` `executeFetch`, so `/execute/*` itself keeps a live session alive (the durable fix; the NoUI warm-up is the client-side stopgap).

### B6 — `HEALTHY` ≠ authenticated/extracted `[medium · integration]`
**Status: docs-only (implemented).** Concise "HEALTHY ≠ authenticated" warnings added to `/noui-record-login` (Step 9) and `/noui-record-workflow` (prerequisite): both explain the 401/403-wrapped-as-200 failure, instruct to pre-warm with `tabby session ensure --profile <slug> --open <auth-url>` (or `--skill <id>`), and to verify one known-authenticated request before trusting output. The deeper detail lives in [concepts.md](concepts.md) / [execute-and-runtime.md](execute-and-runtime.md). No code change.

### B7 — `findHealthySession` is non-deterministic with duplicate HEALTHY rows `[medium · Tabby]`
**Status: Tabby-only → hardening plan.** Purely a Tabby resolver-determinism fix — no NoUI half. → **`plans/tabby/tabby-noui-integration-hardening-plan.md` (B7-tabby):** add an `order:` to `findHealthySession` (`credentials.service.ts:347-366`). Note the verified correction: `SessionEntity` has **no `updated_at`** column, so order by `last_health_check` (the proposed `updated_at` would throw); optionally prefer a non-null `pod_name`. The NoUI B5 warm-up mitigates the *symptom* but not the non-determinism.

---

## C. Security & tenant-isolation findings → moved to the Tabby hardening plan

The security topic (cross-tenant secret mount, global encryption key, missing credential audit, `agent_assertion` impersonation, fail-open worker tenant check, owner-scoping of `GET /sessions/:id`, shared-identity connections, template→profile propagation, token revocation, canary skip) is **entirely Tabby-side**. It has been re-verified against the pinned submodule and moved to:

**→ `plans/tabby/tabby-noui-integration-hardening-plan.md`** (Workstreams 1–3: items C1–C10, with `path:line` evidence, proposed changes, validation, and sequencing).

These bound how safely the tenant-wide template path can ship — resolve or explicitly accept the critical ones (C1 cross-tenant secret mount, C2 global encryption key, C5 fail-open worker check) before opening template creation more broadly.

---

## D. Documentation / DX corrections (NoUI-side)

> **Status — addressed.** D1, D3, D4, D5, D6, D7 and the NoUI-side of D8 (`streaming_mode` removal) are fixed in code and/or docs; D2 was resolved during the `cdp`→`tabby` rename. D1 and D7 were fixed at the source (durable): NoUI emits `credential_types.cookies` as `[{name, volatility}]` objects, and the CLI/backend/verifier default `TABBY_API_URL` is aligned to `:8000`. The remaining Tabby-side cruft (D8's dead `AppTemplatesService.findByPattern` and the inert `credential_ref_default`/`idle_shutdown_seconds` template fields) is tracked in **`plans/tabby/tabby-noui-integration-hardening-plan.md` (D8)**.

### D1 — `credential_types` cookie-shape bug is a NoUI emit bug, not a Tabby bug `[high · docs]`
`/noui-generalize` "Fix A" framed it as a Tabby format bug fixed by one-off SQL. Root cause: NoUI emitted a **string array** of cookie names; Tabby's cookie consumer requires `[{name, volatility}]` objects and stores the DTO verbatim. **Fixed at the source** — `tabby_draft_generator.py` + `auth_plan.py` now emit object form; "Fix A" is reframed as legacy-profile remediation.

### D2 — `/execute/browser` was documented as "future/unavailable" but is live `[high · docs]`
`/noui-generalize` pointed at a `localhost:9222` CDP-WebSocket workaround. `/execute/browser` (15 commands, per-session lock) is shipped and `execute_browser()` exists. **Fixed** during the `cdp`→`tabby` rename.

### D3 — Skills pointed runtime auth at `noui_runtime/auth.py`, but the default mode uses `execute.py` `[high · docs]`
**Fixed** in `/noui-generalize` and `/noui-record-login` — default `tabby` mode uses `execute.py`/`execute_fetch`; `auth.py` is only the `--execution-mode http` path.

### D4 — Profile `version_state` vs Session `HEALTHY` were conflated `[high · docs]`
**Fixed** in `/noui-record-login` — profiles have no HEALTHY state (`STAGING/CANARY/ACTIVE/RETIRED`); `HEALTHY` is a Session state, and `login validate` polls the *sessions* table.

### D5 — Owner-scoping / creator-only semantics were undocumented `[medium · docs]`
**Closed** by this skill ([concepts.md](concepts.md)) — `owner_user_id` scoping + agent-token-vs-federated reach — with a pointer added from `/noui-record-login`.

### D6 — Cloud auth + default-mode incompatibility undocumented `[high · docs]`
**Fixed** in `/noui-setup` + the auth-mode × execution-mode matrix in [execute-and-runtime.md](execute-and-runtime.md). (Note the default `tabby` mode now honors `platform_jwt` after A2.)

### D7 — Port default split-brain `[medium · docs/NoUI]`
**Fixed (durable):** the CLI/backend/verifier defaults + `.env.example` + docs are aligned to `http://localhost:8000` (Tabby's real port).

### D8 — Minor `[low]`
**NoUI-side done:** `browser_policy.streaming_mode='cdp'` (a no-op per Tabby gotcha #18) removed from both emit sites; the `dom_check`-vs-`url_check` SPA trade-off is documented in `/noui-record-login`. **Tabby-side cruft → hardening plan (D8):** dead `AppTemplatesService.findByPattern` and the inert `credential_ref_default`/`idle_shutdown_seconds` template fields.

---

## Sequencing notes (no time estimates)

- **NoUI-side: done.** A1–A4 (NoUI), B1–B6 (NoUI), D1–D8 (NoUI) landed on `feat/noui-tabby-integration` with tests.
- **Tabby-side: see the hardening plan.** `plans/tabby/tabby-noui-integration-hardening-plan.md` carries its own sequencing — unblock A4-tabby + B3-tabby first (they gate the shipped cloud flow), then the quick wins (C3 audit, B7 ordering, C5 fail-closed, B5 idle-timer), then the design-coupled isolation work (C1+C2) and the template cluster (C7/C9/D8/A4 — all touch `autoProvisionFromTemplate`).
- **Lands last — the "hop 3" cloud proof:** a federated `/credentials/request` that actually auto-provisions from a NoUI-emitted template can only be validated after A1+A2 (NoUI, done) **and** A4-tabby + B3-tabby (Tabby plan) are in place, against a live cloud Tabby. Never validated end-to-end to date — see `plans/noui/noui-cloud-tabby-auth-plan.md` and the hardening plan's Validation Plan.

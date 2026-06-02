# Provisioning: how NoUI creates Apps & Profiles, and the App Template path

This is the heart of the skill. It documents **what NoUI does today** (raw App + ServiceProfile creation), **where everything is stored**, and the **App Template path** that Tabby supports but NoUI does not yet use.

Paths: NoUI is `noui/...`; Tabby is `noui/tabby/apps/api/src/...`.

---

## 1. What NoUI provisions today (the raw path)

NoUI provisions Tabby entities through **direct admin REST calls made inline in `cli/main.py`** (via the `_tabby_http` helper, `cli/main.py:544`). The FastAPI backend does **not** call Tabby — it only does local SQLite CRUD and runs the draft generator. (A `compiler/login/tabby_client.py` module exists but is **dead code** — not imported anywhere; ignore it.)

NoUI provisions as a **Tabby Admin** (human JWT): `TABBY_ADMIN_TOKEN` if set, else `POST /login` with `ADMIN_BOOTSTRAP_EMAIL`/`ADMIN_BOOTSTRAP_PASSWORD` from `tabby/.env.local` (`cli/main.py:639`). Admin is required because `POST /admin/profiles` and the promote endpoints are `@Roles('Admin')`. (The agent client and platform-JWT are *runtime* auth, not provisioning.)

There are two entry points, both creating the **same two-step App + ServiceProfile pair**:

### `noui login register <bundle>` (`cmd_login_register`, `cli/main.py:1013`)

1. Load the bundle produced by the draft generator (`compiler/login/tabby_draft_generator.py:generate()`, which builds `application_draft` + `service_profile_draft` dicts — **never a template**).
2. Patch the `application_draft` (force a `dom_check` keepalive on `body`; rewrite `http://localhost`→`https://localhost`) and `POST /apps` → read `app_id` (`cli/main.py:1067`).
3. `POST /admin/profiles` with `{**service_profile_draft, app_id, version: "YY.M.D"}` → read `id` as `profile_db_id` (`cli/main.py:1083`).
4. The profile is left in **`STAGING`** (not promoted). Credentials are **not** set.
5. Write `_provisioned {app_id, profile_db_id, profile_id, version_state: STAGING}` into the bundle JSON, and upsert `tabby/.tabby-noui-client.json` (`apps[profile_id] = {app_id, profile_db_id, credential_ref}`, append `profile_id` to `default_profiles`).

Then `noui login credentials <bundle>` prompts username/password, stores the username + `credential_ref` in the cache, and writes `<PREFIX>_PASSWORD` to `tabby/.env.local`. `noui login validate <bundle>` polls for a **HEALTHY session** (not profile state). `noui tabby session ensure --profile <slug>` spawns the live worker.

> **The STAGING trap.** The documented login happy path (`register → credentials → validate → session ensure`) leaves the profile in `STAGING` unless you promote it. The runtime resolver only matches `ACTIVE`/`CANARY` (`credentials.service.ts:224,268`), so a `STAGING`-only profile `404`s `No active profile` at the first tool call. **Fix (gaps.md B1, now implemented):** promote with `noui login register <bundle> --promote`, the standalone `noui login promote <bundle>`, or `noui login import <session_id> --promote` — all run the same `STAGING → CANARY → ACTIVE` walk as `noui tabby setup`. See [troubleshooting.md](troubleshooting.md) and [gaps.md](gaps.md).

### `noui tabby setup` (local, `cmd_tabby_setup`, `cli/main.py:4167`)

The heavier flow that produces a runnable profile:

1. Admin login → decode JWT for `tenant_id`.
2. Provision/rotate a **`noui` agent client** (`POST /admin/agent-clients` with `allowed_profiles`, or `rotate-secret`), write `TABBY_CLIENT_ID`/`TABBY_CLIENT_SECRET`/`TABBY_API_URL` to `noui/.env` (`cli/main.py:4297,4340`). *This is runtime auth, not provisioning.*
3. For each profile, `_ensure_service_profile` (`cli/main.py:3753`): `POST /apps` (`:3782`) → `POST /admin/profiles` (`:3825`) → **two `POST /admin/profiles/{id}/promote` calls** (`:3838`, `:3852`) walking `STAGING → CANARY → ACTIVE`, with a **direct Postgres `UPDATE`** between them to satisfy the canary gate (`_bypass_canary_gate`, `cli/main.py:3599`, sets `canary_request_count = 5` via `docker compose exec psql`).

### Endpoints NoUI calls to provision

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/login` | Get an Admin JWT (when `TABBY_ADMIN_TOKEN` unset) | email+password |
| `POST` | `/apps` | Create the Application (from `application_draft`) | Admin (or Operator) |
| `POST` | `/admin/profiles` | Create the ServiceProfile in `STAGING` (returns `profile_db_id`) | **Admin** |
| `POST` | `/admin/profiles/{id}/promote` | `STAGING→CANARY`, then `CANARY→ACTIVE` (`tabby setup` only) | **Admin** |
| `POST` | `/admin/agent-clients` | Register the `noui` agent client (runtime auth) | Admin |

**Critical omission:** NoUI never sets `execute_enabled` on the app (verified: no occurrence in `cli/`, `compiler/`, `backend/`). It defaults to `false`. Execute works in local dev only because the locally-spawned worker reads `EXECUTE_ENABLED=true` from `tabby/.env.local` and the API uses `LOCAL_WORKER_URL` — both bypass the app row. See [gaps.md](gaps.md).

### Where identifiers are stored (file-based, no central DB)

- Bundle JSON `_provisioned`: `app_id`, `profile_db_id`, `profile_id`, `version_state`.
- `tabby/.tabby-noui-client.json` (the creds cache): `{client_id, client_secret, default_profiles, apps: {profile_id: {app_id, profile_db_id, credential_ref, username, login_url, login_config}}}`.
- `noui/.env`: `TABBY_API_URL`, `TABBY_CLIENT_ID`, `TABBY_CLIENT_SECRET`, (cloud) `ADOPT_*`, `NOUI_TABBY_AUTH_MODE`.
- `tabby/.env.local`: `ADMIN_BOOTSTRAP_EMAIL/PASSWORD`, `<PREFIX>_PASSWORD` per profile.

---

## 2. Local vs cloud setup

| | `noui tabby setup` (local) | `noui tabby setup --cloud` |
|---|---|---|
| Identity | Admin bootstrap user (human JWT) | Developer's **platform PAT** (`ADOPT_CLIENT_ID`/`ADOPT_CLIENT_SECRET` from `app.adopt.ai/dashboard#/admin-box/`) |
| What it does | Provisions `noui` agent client + ServiceProfiles (→ ACTIVE); writes `TABBY_*` | **Only verifies** the PAT → `/v1/users/api-token` → `/auth/token-exchange` round-trip; writes `ADOPT_*`, `TABBY_API_URL`, `NOUI_TABBY_AUTH_MODE=platform_jwt` (`cli/main.py:4086`) |
| Provisions a connection? | **Yes** (App + Profile, promoted ACTIVE) | **No** — creates **no App, Profile, or Template** |
| Runtime token | `agent_token` (works with default `tabby` runtime) | `platform_jwt` (**ignored by the default `tabby` runtime** — see [execute-and-runtime.md](execute-and-runtime.md)) |
| Prereq | Local Tabby + admin token | The org's **tenant must already exist** in cloud Tabby, else token-exchange `401 Tenant not found` |

> **Two cloud dead-ends, stacked.** `tabby setup --cloud` provisions nothing, *and* the default `tabby` runtime ignores the `platform_jwt` it configured. Today the supported model is "one developer / service principal per tenant," not per-end-user. Multi-user serving is explicitly out of scope in `plans/noui/noui-cloud-tabby-auth-plan.md` §F.

---

## 3. The App Template path (Tabby-built, NoUI-not-built)

This is the mechanism that makes a connection reusable tenant-wide. **Tabby has it fully built; NoUI does not emit templates at all.** (Verified: grep across `cli/ backend/ runtime/ compiler/` returns zero references to app-templates / `profile_name_pattern`.)

### How auto-provisioning works (Tabby side)

There is **no explicit "instantiate" endpoint**. Instantiation is **implicit and lazy**, driven from the credentials path:

1. A **federated** user (platform JWT, `owner_user_id` set) calls `POST /credentials/request {profile_id}`.
2. `resolveActiveProfile` finds no profile owned by them and no NULL-owner shared profile (`credentials.service.ts:228-240`).
3. It calls `autoProvisionFromTemplate(tenantId, profileId, ownerUserId)` (`credentials.service.ts:280`):
   - Look up the template by `{tenant_id, profile_name_pattern: profileId}` (`:286`). No match → `404`.
   - `appsService.create(...)` copying the template's config blocks, then `appRepo.update(app_id, {owner_user_id, template_id})` (`:314`).
   - `profilesService.create(...)` (STAGING), then `profileRepo.update(id, {owner_user_id, version_state: ACTIVE})` — **skips canary** (`:328`).
   - `sessionsService.scale(app_id, 1, ...)` → the controller spins a real worker pod, inheriting `owner_user_id` onto the session.
4. Each tenant user who requests that `profile_id` gets their **own private** App+Profile+Session cloned from the one shared template.

### Template API (Tabby side, `@Controller('admin/app-templates')`)

| Method | Path | Auth | Note |
|---|---|---|---|
| `POST` | `/admin/app-templates` | **Any authenticated user** (own tenant); Admin may override `tenant_id` | No `@Roles` guard (see security gap) |
| `GET` | `/admin/app-templates[?tenant_id=]` | Any authenticated user | |
| `GET` | `/admin/app-templates/:id` | Any authenticated user | |
| `PUT` | `/admin/app-templates/:id` | **Admin** | Triggers propagation to linked apps |
| `DELETE` | `/admin/app-templates/:id` | **Admin** | Linked apps' `template_id` set NULL |

### Template lineage and propagation

`applications.template_id` is the lineage FK (migration 020). On `PUT`, `propagateToLinkedApps` (`app-templates.service.ts:89`) copies `PROPAGATED_FIELDS = [browser_policy, login_config, keepalive_config, export_policy, notification_config]` onto all linked **applications** (chunked by 50). It does **not** touch the per-user `service_profiles` cloned at provision time, and `name`/`profile_name_pattern`/`credential_ref_default`/`idle_shutdown_seconds` are not propagated. So a template edit does not reach already-provisioned users' profiles (a real gap — see [gaps.md](gaps.md)).

### What a NoUI App-Template emitter would need (the unbuilt follow-on)

This is the design intent in `plans/noui/noui-cloud-tabby-auth-plan.md` "Caveat 3" (deferred to an unwritten follow-on). To wire it:

1. **Emit a template, not raw entities.** Add a `register_app_template` path that `POST`s `/admin/app-templates` with `{name, profile_name_pattern, login_config, keepalive_config, export_policy, browser_policy, notification_config}` derived from the same drafts `tabby_draft_generator` already builds.
2. **`profile_name_pattern` MUST equal the runtime `profile_slug`** baked into generated ops (`auth_plan.profile_slug` / `PROFILE_SLUG`), or `autoProvisionFromTemplate` will never match.
3. **Set `execute_enabled: true`** — auto-provisioned apps default it to `false`, which breaks `/execute/fetch` in real K8s (the template has no field for it today; this needs a Tabby change or a post-provision patch).
4. **Fix the `credential_types` cookie shape** to `[{name, volatility}]` objects *before* it lands in `export_policy.credential_types`, or every auto-provisioned user inherits the empty-credential bug.
5. **Use the `platform_jwt` runtime** so the token carries `owner_user_id` and actually triggers auto-provisioning — which means porting `platform_jwt` into the default `tabby` execute adapter (today it's agent-token-only).

### Migrating an existing profile to a template

There is **no tooling** for this today. A NULL-owner profile created directly does not auto-clone for other users (it is served as a single shared row, not reproduced per user). A proposed approach: a `noui tabby template adopt --profile <slug>` command that reads an existing app/profile config and `POST`s a matching `/admin/app-templates` row (`profile_name_pattern = slug`). Note the `COALESCE(owner_user_id,'')` unique index (migration 015) means a NULL-owner and an owner-stamped ACTIVE row cannot coexist for the same `profile_id` — de-duplication is required.

---

## 4. Profile lifecycle reference

```
STAGING ──promote──▶ CANARY ──promote(gated)──▶ ACTIVE ──(new ACTIVE retires old)──▶ RETIRED
   ▲                    │                                                              │
   └──── rollback ──────┘                                  rollback ◀──reactivate parent┘
```

- `STAGING → CANARY`: unconditional.
- `CANARY → ACTIVE`: **gated** — requires `canary_request_count ≥ 5` and error rate ≤ 20% (`packages/shared/src/constants.ts`), and retires the existing ACTIVE for that `(tenant, profile_id)` in a transaction. Canary counters are incremented by the **credentials request path** (`credentials.service.ts:175`), not the (unused) `recordCanaryResult`.
- **Auto-provisioned profiles skip the gate entirely** — created then immediately set `ACTIVE` (`credentials.service.ts:328`).
- `noui tabby setup` bypasses the gate locally by writing `canary_request_count = 5` directly in Postgres.

→ Next: **[execute-and-runtime.md](execute-and-runtime.md)** for how a provisioned profile is consumed at runtime.

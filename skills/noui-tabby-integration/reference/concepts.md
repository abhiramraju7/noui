# Concepts: Tabby's data model, scoping, and auth

This is the foundation for the rest of the skill. Everything is grounded in the pinned Tabby submodule (`noui/tabby`, branch `tabby-noui`). Paths below are relative to `noui/tabby/apps/api/src` unless noted.

---

## 1. The four entities

All four are **tenant-scoped** (every query filters `tenant_id`). There is no global tenant guard — scoping is enforced per service method in the TypeORM `where` clause.

### Application (`entities/application.entity.ts`)
The running unit. A controller reconciliation loop keeps live worker sessions equal to `desired_session_count` (set `0` to idle-shut it down). Notable columns:

- `login_config` (jsonb) — the Login DSL + **`credential_ref`** (how to get the username/password).
- `keepalive_config` (jsonb) — health-check interval + checks (`url_check` / `dom_check` / `network_check`).
- `export_policy` (jsonb) — what to extract, including `credential_types` (the shape) and `target_domains`.
- `target_urls` (jsonb) — egress allowlist.
- `browser_policy` (jsonb) — downloads/clipboard/file_chooser flags. (`streaming_mode` here is a **no-op** — Tabby gotcha #18.)
- `owner_user_id` (varchar, nullable) — per-user scoping key (migration 014). **NULL = shared.**
- `template_id` (uuid, nullable) — lineage: the template this app was auto-provisioned from (`NULL` for manually-created apps; migration 020).
- `execute_enabled` (boolean, default **false**, migration 022) — gates whether the worker mounts the `/execute/*` HTTP routes and (in K8s) whether a worker Service is created.

There is **no ORM relation** from Application → ServiceProfile; the link is the reverse FK `service_profiles.app_id → applications.id` (`ON DELETE RESTRICT`).

### ServiceProfile (`entities/service-profile.entity.ts`)
A **versioned** definition — each row *is* a version (there is no separate version table). Notable columns:

- `profile_id` (varchar) — the **semantic slug** (e.g. `expedia`, `adopt-bank`). This is what callers pass at runtime, **not** the DB UUID.
- `version` (semver), `parent_version_id` (self-FK, for rollback).
- `version_state` enum: **`STAGING → CANARY → ACTIVE → RETIRED`** (default `STAGING`).
- `credential_types` (jsonb) — the **shape + per-field volatility** (`STABLE` / `SEMI_STABLE` / `VOLATILE`). Holds **no secret values**.
- `target_domains` (jsonb), `login_config` (jsonb), `canary_request_count` / `canary_error_count`.
- `owner_user_id` (varchar, nullable). Entity comment: *"Null = shared/tenant-scoped (backward compat)."*

> **Two IDs for one profile.** Runtime calls (`/credentials/request`, `/execute/*`) use the `profile_id` **slug**. Admin calls (`/admin/profiles/:id`, `/promote`) use the `profile_db_id` **UUID**. A documented historical bug embedded the UUID where the slug was expected and `/credentials/request` rejected it.

### Session (`entities/session.entity.ts`)
A live worker pod running an authenticated Playwright/Chromium page. This is what actually performs execute and credential extraction.

- `state` enum: `STARTING / HEALTHY / UNHEALTHY / LOGIN_NEEDED / LOGIN_IN_PROGRESS / FAILED / TERMINATED`.
- `pod_name` (nullable) — used to build the worker URL for `/execute/*`.
- `owner_user_id` (nullable) — **inherited from the app at create time** (`apps/controller/src/reconcile.service.ts:198`).
- `last_credential_request_at` — drives idle-shutdown (updated by `/credentials/request`, **not** by `/execute/*`).

`HEALTHY` only means the keepalive health check passed. It does **not** guarantee login completed or that a credential bundle has been extracted.

### App Template (`entities/app-template.entity.ts`, `modules/app-templates/`)
A tenant-scoped **reusable blueprint** for an App+Profile. The provisioning primitive for tenant-wide reuse.

- `name` (UNIQUE per tenant), `profile_name_pattern` (the **join key** matched against the requested `profile_id` for auto-provisioning).
- The same config blocks as an App: `login_config`, `keepalive_config`, `export_policy`, `browser_policy`, `notification_config`.
- `credential_ref_default` (default `'manual:'`) and `idle_shutdown_seconds` — **accepted but inert**: `autoProvisionFromTemplate` never reads them (`credentials.service.ts:299-330`).
- FK → `tenants(id) ON DELETE CASCADE`; `UNIQUE(tenant_id, name)`; indexed on `(tenant_id, profile_name_pattern)`.

There is **no `execute_enabled`** field on the template (relevant gap — see [gaps.md](gaps.md)).

---

## 2. The two credential systems (do not conflate)

**(a) Login credentials — INPUT** (the username/password used to log in to the target site)
- Referenced by `login_config.credential_ref`. **Only two forms**, validated by `packages/shared/src/dsl.validator.ts:185`:
  - `k8s:secret/{name}` — the worker reads `username`/`password` from a K8s secret mounted at `/var/run/secrets/browser-hitl/{name}/` (`apps/worker/src/credential-resolver.ts:25`); injected into the DSL as `${USERNAME}`/`${PASSWORD}`.
  - `manual:` — no stored secret; a human types it via HITL/VNC.
- **Never stored in Postgres.** The secret name after the prefix is mounted verbatim (`apps/controller/src/pod-manager.service.ts:461`).

**(b) Extracted credentials — OUTPUT** (cookies/headers/CSRF harvested from the live page)
- Encrypted as **AES-256-GCM** artifact bundles in **tenant-scoped MinIO** buckets (`artifact-bundles-{tenantId}`), not in Postgres. Layout `[nonce 12B][ciphertext][authTag 16B]`.
- Decrypted on demand by `POST /credentials/request` using `TENANT_ENCRYPTION_KEY` (`credentials.service.ts:468`), merged with the `credential_types` *shape* into the response envelope.

The `service_profiles.credential_types` column is a **shape declaration only** — which cookies/headers to return + volatility — never secret values.

> **The `credential_types` cookie-shape bug.** The Tabby consumer iterates `credential_types.cookies` expecting **objects** `[{name, volatility}]` (`credentials.service.ts:629`). NoUI emits a **plain string array of cookie names** (`compiler/login/tabby_draft_generator.py:543` + `auth_plan.py:159`). Result: every cookie comes back with `name:""`, `value:""`. Tabby stores the DTO verbatim (`profiles.service.ts:64`), so the defect is on the **NoUI emit side**, and it recurs on every `login register`. Headers tolerate both string and object forms; cookies do **not**. (Documented as `/noui-generalize` "Fix A", but framed as a Tabby bug — see [gaps.md](gaps.md).)

---

## 3. Scoping: `owner_user_id` is the switch

A profile/session is scoped by three things, in this precedence: **`tenant_id`** (always), then **`owner_user_id`**, then (for Agent tokens) **`allowed_profiles`**.

`resolveActiveProfile(tenantId, profileId, ownerUserId)` (`credentials.service.ts:219`) — the resolver used by **both** `/credentials/request` and `/execute/*`:

```
where = { tenant_id, profile_id, version_state IN (ACTIVE, CANARY) }
if (ownerUserId) {                                  // federated/platform-JWT caller
    where.owner_user_id = ownerUserId               // 1. the caller's own profile
    if none:
        where.owner_user_id = IsNull()              // 2. fall back to SHARED (NULL) only
    if still none:
        autoProvisionFromTemplate(...)              // 3. clone a private one from a template
} else {                                            // agent-token caller (no owner_user_id)
    // owner filter skipped entirely → matches ANY owner's row in the tenant
}
prefer ACTIVE over CANARY
```

Key consequences (all verified):

- **NULL-owner profile = tenant-shared.** Served to any user via step 2 (`credentials.service.ts:236`). A genuinely shared single connection *is* a NULL-owner profile.
- **Set-owner profile = per-user / creator-only.** Step 1 is strict equality; step 2 explicitly excludes other users' rows. The spec test "does NOT leak another user's profile in the shared fallback" locks this in.
- **Auto-provision only fires for federated callers** (the `if (ownerUserId)` gate, `credentials.service.ts:244`) **and only via `/credentials/request`** — `/execute/*` calls `resolveActiveProfile` but does **not** wrap it with the auto-provision/rescale recovery (`execute.service.ts:69`).
- **DB-level isolation:** the profile unique indexes were rebuilt as `(tenant_id, profile_id, COALESCE(owner_user_id,''))` (migration 015), so one ACTIVE row can exist **per user** for the same `profile_id`.

`findHealthySession(tenantId, app_id, ownerUserId)` (`credentials.service.ts:347`) applies the identical owner filter — it adds `owner_user_id = ownerUserId` only when `ownerUserId` is set.

---

## 4. Auth modes and multi-tenancy

Tabby is both an OAuth2 authorization server (mints HS256 JWTs) and a resource server (validates external IdP JWTs via JWKS). One passport strategy handles both, keyed on `iss`. Every controller reads scoping off `req.user` (`{user_id, tenant_id, role, token_type, allowed_profiles, owner_user_id, idp_id}`).

`token_type` ∈ `human | service | agent | federated`. The decisive distinction for sharing:

| | Agent token | Platform JWT (federated) |
|---|---|---|
| How | `POST /auth/agent-token` with `client_id`/`client_secret` (client-credentials) | PAT → `POST {ADOPT_API_URL}/v1/users/api-token` → `POST {TABBY_API_URL}/auth/token-exchange` (`subject_token_type: oidc_jwt`) |
| `owner_user_id` | **None** (`auth.service.ts:183`) | **Set** from the IdP `userId`/`sub` claim (`token-exchange.service.ts:138,188`) |
| Reach | **Tenant-wide** for its `allowed_profiles` (owner filter skipped) | **Per-user** (owner-scoped); the only token that can trigger template auto-provisioning |
| Role | `Agent` (gated to `allowed_profiles` on every action) | `Admin` if email domain ∈ `idp.admin_domains`, else `default_role`/`Operator` |
| NoUI uses it for | Default mode for the **`tabby` runtime** (`/execute/fetch`) and the autopilot browser driver | Both the **`tabby`** runtime (when `platform_jwt` is selected — gaps.md A2) and the legacy `--execution-mode http` runtime, plus `tabby setup --cloud` |

Tenancy: `tenant_id` is read from the verified JWT, never the request body for normal callers. `tenants.id` is a **varchar** so a Frontegg org id can be used directly. Token-exchange can auto-create a tenant if `idp.allow_auto_provision` is set; otherwise the tenant **must already exist** or token-exchange returns `Tenant not found` (a known cloud prerequisite). The IdP is a **global singleton** (no `tenant_id` column); multi-tenant routing is via the `tenant_id_claim` on the incoming JWT.

**Agent clients** (`agent_clients` table) are registered only by an Admin (`POST /admin/agent-clients`), carry `allowed_profiles`, and the plaintext secret is returned once. `noui tabby setup` (local) provisions a `noui` agent client for the runtime.

> **`agent_assertion`** is a third token-exchange mode: an agent JWT + `target_user_id` mints a federated (owner-scoped) token on behalf of a user. This is the intended bridge between an agent and per-user profiles — but it currently validates very little about `target_user_id` (see the security findings in [gaps.md](gaps.md)).

---

## 5. The shared-vs-per-user model, stated precisely

| Connection kind | `owner_user_id` | Who can use it | How it comes to exist | Trade-offs |
|---|---|---|---|---|
| **Tenant-shared** | NULL | Any user in the tenant (and any agent token) | Raw `POST /apps` + `POST /admin/profiles` (what NoUI does today); or an agent-token caller | One logged-in identity for everyone; no per-user attribution; one CAPTCHA/lockout hits the whole tenant |
| **Per-user (template-backed)** | set | Only that user | `autoProvisionFromTemplate` on a federated user's first `/credentials/request`, cloned from a tenant `app_template` | Per-user login, attribution, and isolation; the scalable cloud path |
| **Per-user (direct federated)** | set | Only that user | A federated caller hitting a path that stamps owner — in practice only the auto-provision path does this | Same isolation; but no blueprint to reproduce for the next user |

The **template** is the *tenant-wide recipe*; the connections it spawns are *private per user*. "Make this available to all users in the tenant" = "create one template; each user auto-provisions their own." It is **not** "everyone shares one session."

→ Next: **[provisioning.md](provisioning.md)** for what NoUI actually does today vs the template path, and **[execute-and-runtime.md](execute-and-runtime.md)** for how the runtime consumes all of this.

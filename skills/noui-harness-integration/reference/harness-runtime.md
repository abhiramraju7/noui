# The Agent Harness runtime, for skill authors

Ground truth: `adoptai-workflows` branch `feat/agent-harness-web-api-tool` (2026-06-11). Code root: `src/workflows/agent_harness/`.

## What runs a turn

`AgentHarnessTurnWorkflow` (workflow.py) executes ONE conversational turn as a Temporal workflow: a loop of `LLM step → dispatch tools → feed results back` (cap ~100 iterations) until the model stops. It owns a per-conversation **OpenSandbox** container and streams every event to the frontend via Redis (`stream:request:{conversation_id}`); the durable transcript goes to S3.

Entry path: frontend `/agent-v2` → adoptwebui proxy (`backend/app/routes/end_user_agent_harness.py`, magic-link member auth) → workflows API (`api/app/routers/agent_harness.py`, `X-Workflows-Secret`) → Temporal queue `agent-harness-task-queue`.

## The sandbox (what your skill's code actually runs in)

- **Image:** `python:3.11-slim` (ECR mirror; override `OPENSANDBOX_SANDBOX_IMAGE`). `sandbox.py:110-141`.
- **Env: `env=None`.** The harness passes no environment variables into the sandbox — there is nothing to read: no Tabby URL, no client IDs, no org context, no member identity.
- **Network:** open egress, but **unauthenticated**. `curl` works for public endpoints; there is no path from sandbox code to a member-scoped credential.
- **Pre-created dirs:** `/workspace` (always) and `/workstream` (lazy manifest). Conventions:
  - `/workspace/artifacts/` — collected at turn end as conversation outputs
  - `/workspace/skill_assets/<skill>/<path>` — where binary skill aux files land
  - `/workspace/uploads/<turn_id>/` — user-attached files
  - `/workstream/.staging_manifest.json` — lazy docstore file index
- **Timeouts:** 20 min per bash command; sandbox lease 30 min with 120 s keepalives; ~10 min idle grace after a turn.
- **Output caps:** bash stdout/stderr is capped for the model (~100 KB; oversize optionally offloaded to `/workspace/.tool-output/<id>.txt`).
- **No Python deps:** the image is bare slim. Post-processing scripts a skill ships must be **stdlib-only**; per-turn `pip install` is slow, flaky, and an anti-pattern.

## The agent's tool inventory (what your SKILL.md can instruct it to use)

All schemas in `constants.py`; dispatch in `activities.py` (`dispatch_tool_activity`).

| Tool | Side | Use from a skill's perspective |
|---|---|---|
| `bash` | sandbox | Run anything in the sandbox — post-processing, curl for public APIs |
| `fetch_skill` / `read_skill_file` | worker (S3) | How the agent loads SKILL.md and aux files (text inline ≤256 KB; binary → `/workspace/skill_assets/`) |
| `call_web_api` | worker (Tabby) | **The only authenticated HTTP path.** See [call-web-api.md](call-web-api.md) |
| `ws_list` / `ws_read` / `ws_grep` / `ws_add` | worker (S3/docstore) | Workstream document I/O (lazy, budget-capped ~200 MB/session) |
| `save_output` | worker (S3) | Persist a produced file as a conversation output |
| `set_plan` / `start_phase` / `end_phase` / `start_chip` / `reflect` | worker | Narrative timeline (no side effects) |
| `render_ui` / `render_builder` | worker | GenUI output / structured input forms |
| `list_integrations` / `run_integration_tool` | worker (DB/MCP) | Org MCP integrations — unrelated to Tabby skills |
| `memory`, `search_skills` | worker (S3) | Feature-gated (`AGENT_HARNESS_MEMORY_ENABLED`, `AGENT_HARNESS_SKILL_SEARCH_ENABLED`) |

## The skill store (how your skill gets there and resolves)

S3 layout (bucket = `AGENT_BUCKET`, default `adopt-agent-dev`):

```
skills/source=default/skill_name=<name>/SKILL.md [+ aux]
skills/source=org/org_id=<org>/skill_name=<name>/SKILL.md [+ aux]
plugins/source={default,org}/.../skills/<name>/...
```

- **Resolution precedence** (first match wins): org skill → org plugin → default skill → default plugin. **Org override is TOTAL** — an org skill named `foo` fully shadows the default `foo`, aux files included.
- **Upload validation** (`skills_upload.py`): slug `^[a-z0-9][a-z0-9-]*$`, total ≤50 MB (`AGENT_HARNESS_MAX_SKILL_UPLOAD_MB`), valid frontmatter (`name`, `description`), no `..` aux paths.
- **Catalog discovery:** the skill list is rendered into the `fetch_skill` tool *description* each turn — the frontmatter `description` is the only thing that makes a skill discoverable. Same rules as classic NoUI skills: triggers matter.
- **Caches are per worker process:** org catalog 30 s, default catalog 300 s, invalidation is process-local. A fresh upload may be invisible to other workers until TTL (gap G5).

## Aux-file mechanics (how recipes/scripts reach the agent)

`fetch_skill` returns SKILL.md plus an aux-file manifest. `read_skill_file` returns **text files inline** to the model (≤256 KB) — the documented flow is *read file → write into sandbox via `cat > f <<'EOF'` heredoc → run with bash*. Binary aux files are streamed into the sandbox at `/workspace/skill_assets/<skill>/<path>` via presigned GET instead.

Consequence: `operations.json` and any post-processing `.py` your skill ships are read as text and heredoc'd — keep them small and self-contained.

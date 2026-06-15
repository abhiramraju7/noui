# Harness-mode skills: what NoUI emits and why

Generator: `compiler/skill/skill_generator.py` (`execution_mode="harness"`) + `compiler/skill/harness_md_generator.py`. Export:

```bash
noui workflow export <session_id> --as skill --execution-mode harness
```

(`--execution-mode harness` is skill-only; the backend rejects it for `--as mcp`/`both`.)

## Output tree

```
<skill>/
    SKILL.md            # call_web_api operation cards (or curl cards when unauthenticated)
    manifest.json       # runtime.type=agent-harness-skill, execution_strategy=harness_call_web_api
    API.md              # endpoint reference (unchanged format)
    operations.json     # machine-readable request recipes
    auth_plan.json      # when auth was detected (provenance; the harness doesn't read it)
```

Deliberately absent (the whole point): `noui_runtime/`, `operations/*.py`, `pyproject.toml`, `.python-version`. A harness skill ships **knowledge, not transport** — the sandbox must never hold credentials or call Tabby, so there is nothing for shipped code to execute.

## The decision rule: call_web_api vs curl

- **Profile bound (authenticated workflow)** → every operation renders as a `call_web_api` card. The browser session carries the cookies; the harness handles tokens and login.
- **No profile (public endpoints)** → operations render as `bash` curl cards (sandbox egress is open and a worker round-trip buys nothing). The SKILL.md notes the escape hatch: if the site turns out to be bot-protected (429s, challenges), re-export with a Tabby profile bound so calls route through a real browser.
- **`static_secret_header` detected** → the compiler **hard-warns** (Python warning + `manifest.warnings[]` + a ⚠️ callout in SKILL.md): gap G1 means there is no safe place for the secret in the harness. Export classic instead.

## Operation cards

Each recorded operation becomes a SKILL.md section the agent copies directly:

```json
{
  "app": "expedia",
  "url": "https://www.expedia.com/api/v1/typeahead/<destination>",
  "method": "GET"
}
```

plus a parameter table with an **In** column (`path` / `query` / `body`) and `<param>` placeholders in the URL/body. `operations.json` carries the same recipes machine-readable:

```json
{
  "schema_version": "1",
  "operations": [
    {
      "name": "search_hotels",
      "description": "...",
      "tool": "call_web_api",
      "app": "expedia",
      "method": "GET",
      "url_template": "https://www.expedia.com/Hotel-Search",
      "path_params": [],
      "query_params": [{"name": "destination", "type": "string", "required": true}],
      "body_params": [],
      "headers": {"x-csrf": "..."}
    }
  ]
}
```

## Manifest differences vs classic skills

| Field | Classic (`tabby`/`http`) | Harness |
|---|---|---|
| `runtime.type` | `claude-code-skill` | `agent-harness-skill` |
| `runtime.operation_style` | `subprocess-cli` | `call_web_api` |
| `runtime.python*` | present | absent |
| `auth.execution_strategy` | `tabby_execute_fetch` / auth strategy | `harness_call_web_api` |
| `operations[].module`/`entry` | `operations/<op>.py` / `execute` | absent — `recipe: operations.json`, `tool: call_web_api\|bash` |
| `warnings` | — | present when G1 fires |

## Post-processing pattern

The harness agent glues fetch and shaping itself. The recommended SKILL.md guidance (already emitted):

1. Call `call_web_api`, get the JSON text result.
2. Save it into the sandbox: `cat > /workspace/<op>.json <<'EOF' … EOF` via bash.
3. Shape with stdlib Python (`json`, `csv`, `re`) in the sandbox.

If a workflow needs heavyweight, reusable shaping, ship it as a small **stdlib-only** aux script the agent heredocs in — never a script that fetches.

## Operational constraints to bake into recipes

- **Pagination beats truncation:** results cap at ~20k chars. Where the recorded API supports page/limit params, keep them as parameters and document defaults.
- **No binary endpoints** (G2): drop or annotate recorded operations whose response is a file/PDF — they cannot cross `call_web_api` today.
- **Origin discipline** (G3): the profile's login flow must end on the target site's origin or fetches 502.
- **Publishing:** zip the tree and upload via the harness skill-upload route (org-scoped). Slug `^[a-z0-9][a-z0-9-]*$`, ≤50 MB. Expect up to ~30 s of catalog staleness across workers (G5).

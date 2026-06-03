# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Cloud Tabby auth via platform token-exchange.** Generated MCP servers/Skills
  and the compile-time auth verifier can authenticate against a cloud/staging
  Tabby by exchanging a platform Personal Access Token for a platform JWT
  (`POST /v1/users/api-token`), then for a Tabby JWT (`POST /auth/token-exchange`),
  in addition to the local `/auth/agent-token` flow. The flow is selected by
  `NOUI_TABBY_AUTH_MODE` (auto-detects `platform_jwt` when `ADOPT_API_URL` +
  `ADOPT_CLIENT_ID` + `ADOPT_CLIENT_SECRET` are set, else `agent_token`). The
  exchanged bearer is cached in-process until shortly before expiry.
- `noui tabby setup --cloud` — verifies the PAT → platform-JWT → Tabby round-trip
  and writes the cloud env vars to `.env` (no local Tabby or admin token needed).

### Changed

- **BREAKING: `TABBY_API_HOST` and `TABBY_API_URL` collapsed into a single
  `TABBY_API_URL`.** Every env read now uses `TABBY_API_URL`; `TABBY_API_HOST` is
  no longer read (no fallback). Rename it in your `.env`/environment.
- **Default execution mode for generated MCP servers and Skills is the `tabby`
  mode** (`--execution-mode tabby`). Generated operations call Tabby's
  `POST /execute/fetch` endpoint over plain HTTP; the Tabby worker runs
  `fetch(url, {credentials: 'include'})` inside the real authenticated browser,
  so cookies and TLS fingerprint come from the browser. Sidesteps Akamai /
  Cloudflare false positives that fire on Python HTTP clients. (This mode was
  previously named `cdp`; renamed to `tabby` because the runtime no longer opens
  a client-side CDP/WebSocket connection.)
- **Removed the dead client-side CDP-WebSocket adapter**
  (`compiler/runtime/cdp_adapter.py`) and the related `mcp status` CDP-reachability
  probe. `--execution-mode cdp` is no longer accepted — use `tabby` (the default).
- `auth.execution_strategy` added to `manifest.json` (additive, non-breaking):
  `"tabby_execute_fetch"` under the default; mirrors `auth.strategy` under
  `--execution-mode http`. Existing readers of `auth.strategy` are unaffected.
- `/noui-record-workflow` skill documents the `tabby` default under *How
  Execution Works*; `/noui-generalize` reframed around hand-edit cases on top
  of the default (SPA DOM scraping, HITL login). New `/noui-tabby-integration`
  reference skill documents Tabby provisioning, `owner_user_id` scoping, the
  execute runtime, and the end-to-end integration gaps.
- Compiler now rejects empty, malformed, or no-API HARs early with
  `HarValidationError` instead of silently generating MCP servers or Skills
  with zero tools. The workflow export endpoint (`POST /workflow/.../export`)
  returns `422 Unprocessable Entity` with the validation message for these
  cases and reserves `500` for unexpected bugs. No output artifacts
  (`server.py`, `tools.json`, `SKILL.md`, `manifest.json`) are written on
  failure.
- CLI now loads the repo-root `.env` (matching `backend/config.py`) so
  `TABBY_API_HOST` set in `.env` is honoured by every `noui` subcommand
  instead of being silently ignored. Values without a scheme (e.g.
  `localhost:8080`) are normalised to `http://localhost:8080` and trailing
  slashes are stripped, eliminating opaque `urlopen` failures.

### Added

- `compiler/runtime/execute_adapter.py` — generates `noui_runtime/execute.py` in
  tabby-mode output, exposing `execute_fetch` and `execute_browser` (calls Tabby's
  `/execute/*` endpoints over plain HTTP).
- `--execution-mode {tabby,http}` flag on `noui workflow export` and
  `noui autopilot export`; corresponding query param on the backend export
  endpoint.
- Explicit `httpx` runtime dependency in `pyproject.toml` (was previously
  transitive). `websockets` remains for the CLI's worker CDP-navigation bridge.
- 18 new tests covering tabby-default invariants and the `--execution-mode http`
  opt-in for both MCP and Skill outputs.

### Notes

- Existing generated servers under `workbench/mcp_servers/` are **not**
  rewritten. Re-exporting an old recording will produce tabby-mode output;
  pass `--execution-mode http` to reproduce the legacy shape.
- `auth.strategy` is unchanged and remains the credential-source descriptor
  (`tabby_credentials` / `static_secret_header`). Only execution mechanics
  changed, not credential classification.

## [1.0.0] - 2026-04-17

Initial open-source release.

### Added

- Public MIT license.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- Tabby pinned as a git submodule tracking the `tabby-noui` branch at SHA
  `d212467`. NoUI's CLI now resolves `TABBY_DIR` to the in-repo submodule by
  default; set `TABBY_DIR` to point at a sibling checkout.
- Issue and pull-request templates under `.github/`.
- Dependabot configuration for `pip` and `github-actions`.
- Secrets-scan and extension-lint jobs in CI.
- Chrome extension: configurable backend URL via popup Settings and
  `homepage_url` in the manifest.

### Changed

- Unified version to `1.0.0` across `pyproject.toml`, `extension/manifest.json`,
  and this changelog.
- Replaced internal fixture references (`adopt-bank` → `example-bank`).

[Unreleased]: https://github.com/adoptai/noui/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/adoptai/noui/releases/tag/v1.0.0

# Troubleshooting harness-mode skills

Symptom → cause → fix, for skills running inside Agent Harness conversations. Platform-level gaps (G1–G5) are tracked in `plans/adoptai-workflows/agent-harness-call-web-api-gaps.md`; this table is the operational view.

| Symptom | Cause | Fix |
|---|---|---|
| `forbidden` from every `call_web_api` | The profile (`app`) is not in the harness agent client's `allowed_profiles`, or is not ACTIVE (STAGING/RETIRED) | Admin: add the profile to the agent client's ACL; promote to ACTIVE (`noui tabby setup` promotes; the login flow alone leaves STAGING — see /noui-tabby-integration) |
| `login_required` on first use | Expected — the member has no live Tabby session for this profile yet | Show the returned `login_url` to the user; retry the identical call with `wait_for_login: true` |
| `login_required` loops forever | Login link expired (10 min), or the member logs into a different profile/app than `app` | Re-issue the call to get a fresh link; verify the `app` slug matches the recorded profile |
| `login_timeout` | User didn't finish login within ~180 s of the `wait_for_login` retry | Ask the user to complete login, then retry. Not an error state |
| Response cuts off mid-JSON | Harness text cap (~20k chars, `AGENT_HARNESS_TABBY_RESULT_CAP_CHARS`) | Use the recipe's pagination/filter params; never re-fetch the same oversized URL. If the endpoint can't be narrowed, this is gap G2 territory |
| 502 / `Failed to fetch` | Page-origin (CORS): the profile's browser session is parked on a different origin than the target URL (gap G3) | Re-record the login so its DSL ends on the target site's origin; confirm with /noui-tabby-integration execute-and-runtime doc |
| Binary/PDF endpoint returns garbage or truncates | `call_web_api` is text-only (gap G2) | Don't route binaries through the tool. Until the platform fix, such operations are not harness-executable |
| Compiler warned `static secret header` at export | The recorded auth is an API key, not cookies (gap G1) | Keep this workflow on the classic path (`--execution-mode tabby` + MCP/local skill). The harness has no safe secret store yet |
| Skill missing from harness catalog right after upload | Per-process catalog caches (org 30 s / default 300 s, process-local invalidation — gap G5) | Wait out the TTL or retry next turn; for repeated publish flows, this is the known Redis-invalidation follow-up |
| Skill loads but agent runs `uv sync`/`.venv` commands that fail | The skill was exported in classic mode, not harness mode | Re-export with `--execution-mode harness`; harness SKILL.md must contain no venv/script mechanics |
| Agent tries to `curl` an authenticated endpoint and gets 401 | Sandbox egress is unauthenticated; the recipe should have been a `call_web_api` card | Check the export: profile-bound workflows must render `call_web_api` cards. If the profile wasn't bound at export time, re-export with `--profile-slug` |

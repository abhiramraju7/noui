"""Bounded browser workflows and discovery helpers for travel skills."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from noui_runtime.execute import execute_browser
from noui_runtime.meta import ALLOWED_HOSTS, PLATFORM, PROFILE, _har_requests, _prices

_MAX_ACTIONS = 20
_TRANSACTIONAL = re.compile(
    r"\b(book|buy|pay|purchase|reserve|confirm|checkout|place order|complete booking)\b",
    re.I,
)
_ALLOWED_ACTIONS = {
    "click_text",
    "click_selector",
    "type_label",
    "type_selector",
    "press_key",
    "select_option",
    "scroll",
    "wait_selector",
    "wait_url",
}


def _validate_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in ALLOWED_HOSTS:
        raise ValueError(f"url must be an HTTPS {PLATFORM} URL")
    return url


def _command(action: dict[str, Any], allow_transactional: bool) -> tuple[str, dict[str, Any]]:
    kind = str(action.get("action") or "")
    if kind not in _ALLOWED_ACTIONS:
        raise ValueError(f"unsupported browser action: {kind!r}")
    if kind == "click_text":
        text = str(action.get("text") or "").strip()
        if not text:
            raise ValueError("click_text requires text")
        if _TRANSACTIONAL.search(text) and not allow_transactional:
            raise ValueError(
                "transactional click blocked; pass allow_transactional=true explicitly"
            )
        return "click_by_text", {"text": text, "exact": bool(action.get("exact", False))}
    if kind == "click_selector":
        return "click_element", {"selector": str(action.get("selector") or "")}
    if kind == "type_label":
        return "type_into_label", {
            "label": str(action.get("label") or ""),
            "text": str(action.get("text") or ""),
        }
    if kind == "type_selector":
        return "type_text", {
            "selector": str(action.get("selector") or ""),
            "text": str(action.get("text") or ""),
            "clearFirst": bool(action.get("clear_first", True)),
        }
    if kind == "press_key":
        params = {"key": str(action.get("key") or "")}
        if action.get("selector"):
            params["selector"] = str(action["selector"])
        return "press_key", params
    if kind == "select_option":
        return "select_option", {
            "selector": str(action.get("selector") or ""),
            "value": str(action.get("value") or ""),
        }
    if kind == "scroll":
        amount = max(-3000, min(3000, int(action.get("amount", 700))))
        return "scroll_page", {"dy": amount}
    if kind == "wait_selector":
        return "wait_for_selector", {
            "selector": str(action.get("selector") or "body"),
            "timeout": min(30_000, max(100, int(action.get("timeout_ms", 10_000)))),
        }
    return "wait_for_url", {
        "url_substring": str(action.get("url_substring") or ""),
        "timeout": min(30_000, max(100, int(action.get("timeout_ms", 10_000)))),
    }


def _safe_action_log(kind: str, params: dict[str, Any], result: Any) -> dict[str, Any]:
    logged = dict(params)
    if "text" in logged and kind in {"type_into_label", "type_text"}:
        logged["text"] = "<redacted>"
    return {"command": kind, "params": logged, "result": result}


async def run_browser_tools(
    *,
    url: str,
    mode: str = "inspect",
    actions: list[dict[str, Any]] | None = None,
    screenshot: bool = False,
    allow_transactional: bool = False,
    profile_slug: str = PROFILE,
) -> dict[str, Any]:
    """Inspect a page or run a bounded browser workflow with HAR discovery."""
    _validate_url(url)
    if mode not in {"inspect", "workflow", "discover"}:
        raise ValueError("mode must be inspect, workflow, or discover")
    actions = actions or []
    if len(actions) > _MAX_ACTIONS:
        raise ValueError(f"at most {_MAX_ACTIONS} browser actions are allowed")
    if mode == "inspect" and actions:
        raise ValueError("inspect mode does not accept actions")

    har_started = False
    har_data: dict[str, Any] = {}
    action_log: list[dict[str, Any]] = []
    try:
        await execute_browser(profile_slug, "har_start")
        har_started = True
        await execute_browser(profile_slug, "navigate", {"url": url}, timeout_ms=60_000)
        await execute_browser(
            profile_slug,
            "wait_for_selector",
            {"selector": "body", "timeout": 15_000},
            timeout_ms=20_000,
        )
        for action in actions:
            await execute_browser(profile_slug, "get_page_summary")
            command, params = _command(action, allow_transactional)
            result = await execute_browser(profile_slug, command, params, timeout_ms=35_000)
            action_log.append(_safe_action_log(command, params, result))
        summary = await execute_browser(profile_slug, "get_page_summary")
        page_info = await execute_browser(profile_slug, "get_page_info")
        screenshot_data = (
            await execute_browser(profile_slug, "screenshot", timeout_ms=60_000)
            if screenshot
            else None
        )
    finally:
        if har_started:
            try:
                har_data = await execute_browser(profile_slug, "har_stop", timeout_ms=60_000) or {}
            except RuntimeError:
                pass

    visible_text = " ".join(
        str(element.get("text") or "") for element in summary.get("elements", [])
    )
    return {
        "platform": PLATFORM,
        "mode": mode,
        "page": page_info,
        "summary": summary,
        "prices": _prices(visible_text),
        "actions": action_log,
        "network_requests": _har_requests(har_data, limit=50),
        "screenshot": screenshot_data,
        "transactional_actions_enabled": allow_transactional,
    }

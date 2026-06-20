"""Contract tests for bounded OTA browser and snapshot capabilities."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BROWSER_FILES = sorted((ROOT / "skills").glob("*/noui_runtime/browser_tools.py"))
SNAPSHOT_FILES = sorted((ROOT / "skills").glob("*/operations/snapshot.py"))


def _load_browser(path: Path):
    meta_path = path.with_name("meta.py")
    package = types.ModuleType("noui_runtime")
    execute = types.ModuleType("noui_runtime.execute")
    auth = types.ModuleType("noui_runtime.auth")

    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("adapter not configured in unit test")

    async def no_auth():
        return {}

    execute.execute_fetch = unavailable
    execute.execute_browser = unavailable
    auth.resolve_auth = no_auth
    sys.modules["noui_runtime"] = package
    sys.modules["noui_runtime.execute"] = execute
    sys.modules["noui_runtime.auth"] = auth

    meta_spec = importlib.util.spec_from_file_location("noui_runtime.meta", meta_path)
    assert meta_spec and meta_spec.loader
    meta = importlib.util.module_from_spec(meta_spec)
    meta_spec.loader.exec_module(meta)
    sys.modules["noui_runtime.meta"] = meta

    name = f"browser_tools_{path.parent.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", BROWSER_FILES, ids=lambda path: path.parent.parent.name)
def test_browser_tools_restrict_hosts_and_transactional_clicks(path: Path) -> None:
    module = _load_browser(path)
    with pytest.raises(ValueError, match="HTTPS"):
        module._validate_url("https://example.invalid/results")
    with pytest.raises(ValueError, match="transactional click blocked"):
        module._command({"action": "click_text", "text": "Confirm booking"}, False)


def test_browser_workflow_captures_har_screenshot_and_redacts_typed_text(monkeypatch) -> None:
    module = _load_browser(BROWSER_FILES[0])
    calls: list[tuple[str, dict]] = []

    async def browser(_profile, command, params=None, **_kwargs):
        calls.append((command, params or {}))
        if command == "get_page_summary":
            return {
                "url": f"https://{next(iter(module.ALLOWED_HOSTS))}/results",
                "title": "Results",
                "elements": [{"text": "Hotel ₹5000"}],
            }
        if command == "get_page_info":
            return {"title": "Results", "url": calls[1][1]["url"]}
        if command == "har_stop":
            return {
                "har": {
                    "log": {
                        "entries": [
                            {
                                "request": {"method": "POST", "url": "https://api.test/graphql"},
                                "response": {
                                    "status": 200,
                                    "content": {"mimeType": "application/json"},
                                },
                            }
                        ]
                    }
                }
            }
        if command == "screenshot":
            return {"file_path": "/tmp/result.png"}
        return {"ok": True}

    monkeypatch.setattr(module, "execute_browser", browser)
    host = next(iter(module.ALLOWED_HOSTS))
    result = asyncio.run(
        module.run_browser_tools(
            url=f"https://{host}/results",
            mode="workflow",
            actions=[{"action": "type_label", "label": "Destination", "text": "London"}],
            screenshot=True,
        )
    )

    assert result["actions"][0]["params"]["text"] == "<redacted>"
    assert result["prices"] == [{"currency": "₹", "amount": 5000.0}]
    assert result["network_requests"][0]["url"] == "https://api.test/graphql"
    assert result["screenshot"]["file_path"] == "/tmp/result.png"
    assert calls[-1][0] == "har_stop"


def _load_snapshot(path: Path):
    meta = types.ModuleType("noui_runtime.meta")
    meta.PROFILE = "test-profile"

    async def search(**_kwargs):
        return {}

    meta.run_public_search = search
    sys.modules["noui_runtime.meta"] = meta
    name = f"snapshot_{path.parent.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_comparison_reports_price_changes() -> None:
    module = _load_snapshot(SNAPSHOT_FILES[0])
    previous = {"source_url": "https://test", "prices": [{"currency": "USD", "amount": 100}]}
    current = {"source_url": "https://test", "prices": [{"currency": "USD", "amount": 90}]}
    comparison = module._compare(previous, current)
    assert comparison["changed"] is True
    assert comparison["added_prices"] == [{"amount": 90, "currency": "USD"}]
    assert comparison["removed_prices"] == [{"amount": 100, "currency": "USD"}]

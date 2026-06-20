"""Contract tests for generated OTA hybrid runtimes."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
META_FILES = sorted((ROOT / "skills").glob("*/noui_runtime/meta.py"))


def _load_meta(path: Path):
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

    name = f"ota_meta_{path.parent.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", META_FILES, ids=lambda path: path.parent.parent.name)
def test_build_url_stays_on_an_allowed_host(path: Path) -> None:
    module = _load_meta(path)
    url = module._build_url(
        query="London",
        origin="DEL",
        destination="London",
        departure="2026-08-10",
        return_date="2026-08-12",
        check_in="2026-08-10",
        check_out="2026-08-12",
        pickup="LHR",
        dropoff="London",
        adults=2,
    )
    parsed = module.urllib.parse.urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc in module.ALLOWED_HOSTS


def test_auto_falls_back_to_browser_and_returns_har_metadata(monkeypatch) -> None:
    module = _load_meta(META_FILES[0])

    async def fetch_failure(*_args, **_kwargs):
        raise RuntimeError("browser fetch wrapper blocked")

    async def browser_success(url, _profile, _query):
        return {
            "title": "London results",
            "url": url,
            "records": [{"id": "1", "name": "London result", "url": url}],
            "summary": "Rendered results",
            "network_requests": [
                {"method": "GET", "url": f"{url}/api", "status": 200, "mime_type": "json"}
            ],
        }

    monkeypatch.setattr(module, "_fetch", fetch_failure)
    monkeypatch.setattr(module, "_browser_snapshot", browser_success)
    result = asyncio.run(module.run_public_search(destination="London"))

    assert result["transport"] == "execute_browser"
    assert result["results_count"] == 1
    assert result["network_requests"][0]["status"] == 200
    assert "browser fetch wrapper blocked" in result["warnings"]


def test_auto_uses_guarded_http_after_tabby_paths_fail(monkeypatch) -> None:
    module = _load_meta(META_FILES[0])

    async def failure(*_args, **_kwargs):
        raise RuntimeError("unavailable")

    async def direct_success(url):
        return f'<html><title>London</title><a href="{url}">London hotel $123</a></html>'

    monkeypatch.setattr(module, "_fetch", failure)
    monkeypatch.setattr(module, "_browser_snapshot", failure)
    monkeypatch.setattr(module, "_direct_fetch", direct_success)
    result = asyncio.run(module.run_public_search(destination="London"))

    assert result["transport"] == "http"
    assert result["results_count"] == 1
    assert result["prices"] == [{"currency": "$", "amount": 123.0}]
    assert len(result["warnings"]) == 2


def test_invalid_transport_is_rejected() -> None:
    module = _load_meta(META_FILES[0])
    with pytest.raises(ValueError, match="transport must be"):
        asyncio.run(module.run_public_search(destination="London", transport="cdp"))


def test_har_metadata_prioritizes_data_endpoints() -> None:
    module = _load_meta(META_FILES[0])
    har = {
        "har": {
            "log": {
                "entries": [
                    {
                        "request": {"method": "GET", "url": "https://cdn.example/app.css"},
                        "response": {"status": 200, "content": {"mimeType": "text/css"}},
                    },
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.example/graphql/search?session_token=secret&locale=en",
                        },
                        "response": {
                            "status": 200,
                            "content": {"mimeType": "application/json"},
                        },
                    },
                ]
            }
        }
    }
    requests = module._har_requests(har)
    assert requests == [
        {
            "method": "POST",
            "url": "https://api.example/graphql/search?session_token=%3Credacted%3E&locale=en",
            "status": 200,
            "mime_type": "application/json",
        }
    ]

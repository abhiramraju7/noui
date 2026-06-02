"""Unit tests for Tabby-related CLI helpers and commands.

Covers behaviour added in the "improve Tabby CLI failure messages" PR:

1. ``_tabby_http`` translates ``urllib.error.HTTPError`` and connection /
   timeout failures into a single ``RuntimeError`` with an actionable message.
2. ``_get_sessions`` swallows errors by default but propagates them when
   ``raise_on_error=True`` (used by the login-validate polling loop).
3. ``cmd_login_validate`` surfaces the last polling error on timeout instead
   of dropping it silently.
4. ``cmd_login_register`` prints the human-friendly profile slug as
   ``Tabby profile ID`` rather than repeating the database UUID.
"""

from __future__ import annotations

import io
import json
import socket
import sys
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_NOUI_ROOT = Path(__file__).resolve().parent.parent
if str(_NOUI_ROOT) not in sys.path:
    sys.path.insert(0, str(_NOUI_ROOT))

from cli import main as cli_main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for ``urllib.request.urlopen`` context-manager output."""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@contextmanager
def _patched_urlopen(side_effect):
    """Patch ``urllib.request.urlopen`` for the duration of the test."""
    with patch.object(cli_main.urllib.request, "urlopen", side_effect=side_effect) as p:
        yield p


def _make_http_error(code: int, body: str = "{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://localhost:8080/whatever",
        code=code,
        msg="test",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(body.encode()),
    )


# ---------------------------------------------------------------------------
# 1. _tabby_http transport / HTTP error handling
# ---------------------------------------------------------------------------


class TestTabbyHttpErrors:
    def test_happy_path_returns_parsed_json(self) -> None:
        with _patched_urlopen(side_effect=lambda *_a, **_k: _FakeResponse({"ok": True})):
            result = cli_main._tabby_http("GET", "/health/live")
        assert result == {"ok": True}

    def test_http_error_preserves_status_and_body(self) -> None:
        # Regression: existing behaviour must keep working unchanged.
        err = _make_http_error(401, '{"detail":"unauthorized"}')
        with _patched_urlopen(side_effect=err), pytest.raises(RuntimeError) as exc_info:
            cli_main._tabby_http("GET", "/admin/profiles", token="bad")
        msg = str(exc_info.value)
        assert "HTTP 401" in msg
        assert "unauthorized" in msg
        assert "/admin/profiles" in msg

    def test_connection_refused_is_actionable(self) -> None:
        # Simulate the Tabby API not running at all.
        err = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
        with _patched_urlopen(side_effect=err), pytest.raises(RuntimeError) as exc_info:
            cli_main._tabby_http("GET", "/health/live")
        msg = str(exc_info.value)
        assert "Cannot reach Tabby" in msg
        assert cli_main.TABBY_API_HOST in msg
        assert "noui tabby status" in msg
        # The underlying OS error should be visible to the user.
        assert "Connection refused" in msg

    def test_dns_failure_is_actionable(self) -> None:
        # gaierror is the typical DNS-level failure surfaced as URLError.
        err = urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided"))
        with _patched_urlopen(side_effect=err), pytest.raises(RuntimeError) as exc_info:
            cli_main._tabby_http("GET", "/health/live")
        msg = str(exc_info.value)
        assert "Cannot reach Tabby" in msg
        assert "nodename" in msg or "servname" in msg

    def test_timeout_is_named_explicitly(self) -> None:
        # urllib wraps socket-level timeouts in URLError(reason=TimeoutError(...)).
        err = urllib.error.URLError(TimeoutError("timed out"))
        with _patched_urlopen(side_effect=err), pytest.raises(RuntimeError) as exc_info:
            cli_main._tabby_http("GET", "/health/live", timeout=7)
        msg = str(exc_info.value)
        assert "Cannot reach Tabby" in msg
        assert "timed out after 7s" in msg


# ---------------------------------------------------------------------------
# 2. _get_sessions raise_on_error toggle
# ---------------------------------------------------------------------------


class TestGetSessions:
    def test_default_swallows_errors(self) -> None:
        with patch.object(cli_main, "_tabby_http", side_effect=RuntimeError("boom")):
            assert cli_main._get_sessions("tok") == []

    def test_raise_on_error_propagates(self) -> None:
        with (
            patch.object(cli_main, "_tabby_http", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            cli_main._get_sessions("tok", raise_on_error=True)

    def test_returns_list_payload(self) -> None:
        sessions = [{"id": "abc", "state": "HEALTHY"}]
        with patch.object(cli_main, "_tabby_http", return_value={"data": sessions}):
            assert cli_main._get_sessions("tok") == sessions


# ---------------------------------------------------------------------------
# 3. cmd_login_validate surfaces the last polling error on timeout
# ---------------------------------------------------------------------------


class TestLoginValidateErrorSurfacing:
    def _bundle_path(self, tmp_path: Path) -> Path:
        bundle = {
            "_provisioned": {
                "app_id": "app-uuid-1234",
                "profile_db_id": "db-uuid-5678",
                "profile_id": "my-app",
            }
        }
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps(bundle))
        return path

    def _drive_polling_loop(self, monkeypatch: pytest.MonkeyPatch) -> list[float]:
        """Patch time so the 60s polling loop completes in two iterations."""
        ticks = iter([100.0, 100.5, 101.0, 200.0])  # last tick exits the loop
        used: list[float] = []

        def fake_time() -> float:
            t = next(ticks)
            used.append(t)
            return t

        monkeypatch.setattr(cli_main.time, "time", fake_time)
        monkeypatch.setattr(cli_main.time, "sleep", lambda _s: None)
        return used

    def test_timeout_includes_last_polling_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bundle = self._bundle_path(tmp_path)
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(
            cli_main,
            "_get_sessions",
            lambda _t, raise_on_error=False: (_ for _ in ()).throw(
                RuntimeError("Cannot reach Tabby at http://localhost:8080 (Connection refused)")
            ),
        )
        self._drive_polling_loop(monkeypatch)

        rc = cli_main.cmd_login_validate(SimpleNamespace(bundle_file=str(bundle)))
        assert rc == 1
        out = capsys.readouterr().out
        assert "Last polling error" in out
        assert "Connection refused" in out

    def test_timeout_without_errors_keeps_classic_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # If polling succeeds but never finds a HEALTHY session, the existing
        # "noui tabby session ensure" hint must still be the message shown.
        bundle = self._bundle_path(tmp_path)
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_get_sessions", lambda _t, raise_on_error=False: [])
        self._drive_polling_loop(monkeypatch)

        rc = cli_main.cmd_login_validate(SimpleNamespace(bundle_file=str(bundle)))
        assert rc == 1
        out = capsys.readouterr().out
        assert "Last polling error" not in out
        assert "noui tabby session ensure" in out


# ---------------------------------------------------------------------------
# 4. cmd_login_register prints the slug, not the DB UUID, as profile ID
# ---------------------------------------------------------------------------


class TestLoginRegisterOutput:
    def test_tabby_profile_id_is_the_slug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bundle = {
            "validation": {"generator_valid": True},
            "application_draft": {
                "name": "MyApp",
                "target_urls": ["https://example.com"],
                "login_config": {"credential_ref": "k8s:secret/tabby-my-app"},
            },
            "service_profile_draft": {
                "profile_id": "my-app",
                "version": "0.0.0",
            },
        }
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(bundle))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_load_cache", lambda: {})
        monkeypatch.setattr(cli_main, "_save_cache", lambda _c: None)

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            if path == "/apps":
                return {"app_id": "app-uuid-1111"}
            if path == "/admin/profiles":
                return {"id": "db-uuid-2222"}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_login_register(SimpleNamespace(bundle_file=str(bundle_path)))
        assert rc == 0

        out = capsys.readouterr().out
        # The slug must appear next to "Tabby profile ID", and the DB UUID must
        # NOT show up there (it still appears next to "ServiceProfile DB ID").
        tabby_line = next(line for line in out.splitlines() if "Tabby profile ID" in line)
        assert "my-app" in tabby_line
        assert "db-uuid-2222" not in tabby_line
        assert "ServiceProfile DB ID" in out


# ---------------------------------------------------------------------------
# 5. tabby setup --cloud (platform-JWT token-exchange onboarding)
# ---------------------------------------------------------------------------


class TestTabbySetupCloud:
    """`tabby setup --cloud` verifies the token-exchange round-trip then writes .env."""

    def _args(self, tmp_path: Path, **over: object) -> SimpleNamespace:
        base: dict = {
            "cloud": True,
            "adopt_api_url": "https://api.adopt.ai",
            "adopt_client_id": "cid",
            "adopt_client_secret": "sec",
            "tabby_url": "https://tabby.cloud",
            "env_file": str(tmp_path / ".env"),
            "profiles": None,
            "force": False,
            "template_bundle": None,
        }
        base.update(over)
        return SimpleNamespace(**base)

    @staticmethod
    def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "ADOPT_API_URL",
            "ADOPT_CLIENT_ID",
            "ADOPT_CLIENT_SECRET",
            "TABBY_API_URL",
            "TABBY_API_HOST",
            "NOUI_TABBY_AUTH_MODE",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_writes_env_on_successful_exchange(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)

        def fake_urlopen(req, *_a, **_k):
            url = req.full_url
            if url.endswith("/v1/users/api-token"):
                return _FakeResponse({"access_token": "PLATFORM_JWT"})
            if url.endswith("/auth/token-exchange"):
                return _FakeResponse({"access_token": "TABBY_JWT"})
            raise AssertionError(f"unexpected url {url}")

        with _patched_urlopen(side_effect=fake_urlopen):
            rc = cli_main.cmd_tabby_setup(self._args(tmp_path))

        assert rc == 0
        env = (tmp_path / ".env").read_text()
        assert "NOUI_TABBY_AUTH_MODE=platform_jwt" in env
        assert "TABBY_API_URL=https://tabby.cloud" in env
        assert "ADOPT_API_URL=https://api.adopt.ai" in env
        assert "ADOPT_CLIENT_ID=cid" in env
        assert "ADOPT_CLIENT_SECRET=sec" in env

    def test_no_bundle_is_auth_verification_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A3: without --template-bundle, --cloud provisions nothing and says so.
        self._clear_env(monkeypatch)
        posted_paths: list[str] = []

        def fake_urlopen(req, *_a, **_k):
            posted_paths.append(req.full_url)
            url = req.full_url
            if url.endswith("/v1/users/api-token"):
                return _FakeResponse({"access_token": "PLATFORM_JWT"})
            if url.endswith("/auth/token-exchange"):
                return _FakeResponse({"access_token": "TABBY_JWT"})
            raise AssertionError(f"unexpected url {url}")

        with _patched_urlopen(side_effect=fake_urlopen):
            rc = cli_main.cmd_tabby_setup(self._args(tmp_path))

        assert rc == 0
        assert not any("/admin/app-templates" in p for p in posted_paths)
        assert "No App Template provisioned" in capsys.readouterr().out

    def test_template_bundle_provisions_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A3: with --template-bundle, --cloud also POSTs /admin/app-templates with
        # the exchanged Tabby JWT and a slug-matched profile_name_pattern.
        self._clear_env(monkeypatch)
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        seen: dict = {}

        def fake_urlopen(req, *_a, **_k):
            url = req.full_url
            if url.endswith("/v1/users/api-token"):
                return _FakeResponse({"access_token": "PLATFORM_JWT"})
            if url.endswith("/auth/token-exchange"):
                return _FakeResponse({"access_token": "TABBY_JWT"})
            if url.endswith("/admin/app-templates"):
                seen["url"] = url
                seen["auth"] = req.get_header("Authorization")
                seen["body"] = json.loads(req.data.decode())
                return _FakeResponse({"id": "tmpl-cloud-1", "profile_name_pattern": "my-app"})
            raise AssertionError(f"unexpected url {url}")

        with _patched_urlopen(side_effect=fake_urlopen):
            rc = cli_main.cmd_tabby_setup(self._args(tmp_path, template_bundle=str(bundle_path)))

        assert rc == 0
        assert seen["url"] == "https://tabby.cloud/admin/app-templates"
        # POSTed with the exchanged (federated) Tabby JWT, not the platform JWT.
        assert seen["auth"] == "Bearer TABBY_JWT"
        assert seen["body"]["profile_name_pattern"] == "my-app"
        assert seen["body"]["execute_enabled"] is True
        assert "tmpl-cloud-1" in capsys.readouterr().out

    def test_template_conflict_is_tolerated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A 409 (template already exists) must not fail cloud setup.
        self._clear_env(monkeypatch)
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        def fake_urlopen(req, *_a, **_k):
            url = req.full_url
            if url.endswith("/v1/users/api-token"):
                return _FakeResponse({"access_token": "PLATFORM_JWT"})
            if url.endswith("/auth/token-exchange"):
                return _FakeResponse({"access_token": "TABBY_JWT"})
            if url.endswith("/admin/app-templates"):
                raise _make_http_error(409, '{"detail":"Template exists"}')
            raise AssertionError(f"unexpected url {url}")

        with _patched_urlopen(side_effect=fake_urlopen):
            rc = cli_main.cmd_tabby_setup(self._args(tmp_path, template_bundle=str(bundle_path)))

        assert rc == 0
        assert "already exists" in capsys.readouterr().out

    def test_missing_creds_returns_error_and_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        args = self._args(
            tmp_path,
            adopt_api_url=None,
            adopt_client_id=None,
            adopt_client_secret=None,
            tabby_url=None,
        )
        rc = cli_main.cmd_tabby_setup(args)
        assert rc == 1
        assert not (tmp_path / ".env").exists()

    def test_token_exchange_failure_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)

        def fake_urlopen(req, *_a, **_k):
            url = req.full_url
            if url.endswith("/v1/users/api-token"):
                return _FakeResponse({"access_token": "PLATFORM_JWT"})
            if url.endswith("/auth/token-exchange"):
                raise _make_http_error(401, '{"detail":"No registered IdP for issuer"}')
            raise AssertionError(f"unexpected url {url}")

        with _patched_urlopen(side_effect=fake_urlopen):
            rc = cli_main.cmd_tabby_setup(self._args(tmp_path))

        assert rc == 1
        assert not (tmp_path / ".env").exists()


# ---------------------------------------------------------------------------
# 6. tabby template create — App Template emitter (A1)
# ---------------------------------------------------------------------------


def _template_bundle() -> dict:
    return {
        "validation": {"generator_valid": True},
        "application_draft": {
            "name": "My App",
            "target_urls": ["https://app.example.com"],
            "login_config": {
                "login_url": "https://app.example.com/login",
                "credential_ref": "k8s:secret/tabby-my-app",
                "steps": [],
            },
            "keepalive_config": {"interval_seconds": 300, "actions": [], "health_checks": []},
            "export_policy": {"artifact_types": ["cookies", "headers"]},
            "notification_config": {"channels": ["slack:#local-dev"]},
            "execute_enabled": True,
        },
        "service_profile_draft": {
            "profile_id": "my-app",
            "credential_types": {
                "cookies": [{"name": "sid", "volatility": "STABLE"}],
                "headers": [],
            },
            "target_domains": ["app.example.com"],
        },
    }


class TestTabbyTemplateCreate:
    def test_posts_template_with_slug_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")

        posted: dict = {}

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            if method == "POST" and path == "/admin/app-templates":
                posted.update(body)
                return {"id": "tmpl-uuid-1", "profile_name_pattern": body["profile_name_pattern"]}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_tabby_template_create(
            SimpleNamespace(bundle_file=str(bundle_path), upsert=False)
        )
        assert rc == 0
        # The match key MUST equal the runtime profile slug.
        assert posted["profile_name_pattern"] == "my-app"
        # credential_types folded into export_policy for autoProvisionFromTemplate.
        assert posted["export_policy"]["credential_types"]["cookies"][0]["name"] == "sid"
        assert posted["execute_enabled"] is True
        out = capsys.readouterr().out
        assert "tmpl-uuid-1" in out

    def test_upsert_updates_on_conflict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")

        calls: list[tuple[str, str]] = []

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            calls.append((method, path))
            if method == "POST" and path == "/admin/app-templates":
                raise RuntimeError('HTTP 409 from POST /admin/app-templates: {"detail":"exists"}')
            if method == "GET" and path == "/admin/app-templates":
                return [{"id": "tmpl-existing", "profile_name_pattern": "my-app"}]
            if method == "PUT" and path == "/admin/app-templates/tmpl-existing":
                return {"id": "tmpl-existing", "profile_name_pattern": body["profile_name_pattern"]}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_tabby_template_create(
            SimpleNamespace(bundle_file=str(bundle_path), upsert=True)
        )
        assert rc == 0
        assert ("POST", "/admin/app-templates") in calls
        assert ("PUT", "/admin/app-templates/tmpl-existing") in calls

    def test_missing_profile_id_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle = _template_bundle()
        del bundle["service_profile_draft"]["profile_id"]
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(bundle))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")

        rc = cli_main.cmd_tabby_template_create(
            SimpleNamespace(bundle_file=str(bundle_path), upsert=False)
        )
        assert rc == 1


class TestLoginRegisterAsTemplate:
    def test_as_template_also_emits_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_load_cache", lambda: {})
        monkeypatch.setattr(cli_main, "_save_cache", lambda _c: None)

        paths: list[str] = []

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            paths.append(path)
            if path == "/apps":
                return {"app_id": "app-1"}
            if path == "/admin/profiles":
                return {"id": "db-1"}
            if path == "/admin/app-templates":
                return {"id": "tmpl-1", "profile_name_pattern": body["profile_name_pattern"]}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_login_register(
            SimpleNamespace(bundle_file=str(bundle_path), as_template=True)
        )
        assert rc == 0
        assert "/admin/app-templates" in paths
        out = capsys.readouterr().out
        assert "App Template ID" in out
        # template_id persisted back into the bundle.
        saved = json.loads(bundle_path.read_text())
        assert saved["_provisioned"]["template_id"] == "tmpl-1"

    def test_default_register_does_not_emit_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(_template_bundle()))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_load_cache", lambda: {})
        monkeypatch.setattr(cli_main, "_save_cache", lambda _c: None)

        paths: list[str] = []

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            paths.append(path)
            if path == "/apps":
                return {"app_id": "app-1"}
            if path == "/admin/profiles":
                return {"id": "db-1"}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_login_register(
            SimpleNamespace(bundle_file=str(bundle_path), as_template=False)
        )
        assert rc == 0
        assert "/admin/app-templates" not in paths


# ---------------------------------------------------------------------------
# 7. execute_enabled: true on app payloads + session-ensure warning (A4)
# ---------------------------------------------------------------------------


class TestExecuteEnabled:
    def test_build_app_payload_sets_execute_enabled(self) -> None:
        cfg = {
            "login_url": "https://app.example.com/login",
            "username": "alice",
            "email_sel": "#email",
            "pass_sel": "#pass",
            "submit_sel": "#submit",
        }
        payload = cli_main._build_app_payload("my-app", cfg)
        assert payload["execute_enabled"] is True

    def test_warn_when_execute_disabled(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            cli_main, "_tabby_http", lambda *a, **k: {"id": "app-1", "execute_enabled": False}
        )
        cli_main._warn_if_execute_disabled("app-1", "tok")
        out = capsys.readouterr().out
        assert "execute_enabled=false" in out

    def test_no_warn_when_execute_enabled(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            cli_main, "_tabby_http", lambda *a, **k: {"id": "app-1", "execute_enabled": True}
        )
        cli_main._warn_if_execute_disabled("app-1", "tok")
        out = capsys.readouterr().out
        assert "execute_enabled" not in out

    def test_warn_is_best_effort_on_lookup_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A failed app lookup must never break session ensure — no raise, no output.
        def boom(*_a, **_k):
            raise RuntimeError("Cannot reach Tabby")

        monkeypatch.setattr(cli_main, "_tabby_http", boom)
        cli_main._warn_if_execute_disabled("app-1", "tok")  # must not raise
        assert "execute_enabled" not in capsys.readouterr().out


class TestPromoteProfileToActive:
    """`_promote_profile_to_active` runs the STAGING→CANARY→ACTIVE walk."""

    def test_happy_path_issues_two_promotes_and_bypasses_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            calls.append(path)
            return {}

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)
        monkeypatch.setattr(cli_main, "_bypass_canary_gate", lambda _id: True)

        assert cli_main._promote_profile_to_active("db-1", "tok") is True
        # Two promote calls (STAGING→CANARY, CANARY→ACTIVE).
        assert calls == ["/admin/profiles/db-1/promote", "/admin/profiles/db-1/promote"]

    def test_canary_gate_failure_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli_main, "_tabby_http", lambda *a, **k: {})
        monkeypatch.setattr(cli_main, "_bypass_canary_gate", lambda _id: False)
        assert cli_main._promote_profile_to_active("db-1", "tok") is False


class TestLoginPromoteCommand:
    """`noui login promote` walks a registered profile to ACTIVE."""

    @staticmethod
    def _bundle(tmp_path: Path, version_state: str = "STAGING") -> Path:
        bundle = {
            "_provisioned": {
                "app_id": "app-1",
                "profile_db_id": "db-1",
                "profile_id": "my-app",
                "version_state": version_state,
            }
        }
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps(bundle))
        return path

    def test_promotes_and_persists_active_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._bundle(tmp_path)
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_promote_profile_to_active", lambda _db, _tok: True)

        rc = cli_main.cmd_login_promote(SimpleNamespace(bundle_file=str(path)))
        assert rc == 0
        persisted = json.loads(path.read_text())
        assert persisted["_provisioned"]["version_state"] == "ACTIVE"

    def test_already_active_is_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = self._bundle(tmp_path, version_state="ACTIVE")
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)

        def _should_not_call(*_a, **_k):  # pragma: no cover - guards against regressions
            raise AssertionError("must not promote an already-ACTIVE profile")

        monkeypatch.setattr(cli_main, "_promote_profile_to_active", _should_not_call)
        rc = cli_main.cmd_login_promote(SimpleNamespace(bundle_file=str(path)))
        assert rc == 0

    def test_unregistered_bundle_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps({"application_draft": {}}))
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        rc = cli_main.cmd_login_promote(SimpleNamespace(bundle_file=str(path)))
        assert rc == 1

    def test_promotion_failure_keeps_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._bundle(tmp_path)
        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_promote_profile_to_active", lambda _db, _tok: False)
        rc = cli_main.cmd_login_promote(SimpleNamespace(bundle_file=str(path)))
        assert rc == 1
        # State must NOT be flipped to ACTIVE on failure.
        persisted = json.loads(path.read_text())
        assert persisted["_provisioned"]["version_state"] == "STAGING"


class TestLoginRegisterPromoteFlag:
    """`noui login register --promote` promotes inline and records ACTIVE."""

    def test_promote_flag_flips_version_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle = {
            "validation": {"generator_valid": True},
            "application_draft": {
                "name": "MyApp",
                "target_urls": ["https://example.com"],
                "login_config": {"credential_ref": "k8s:secret/tabby-my-app"},
            },
            "service_profile_draft": {"profile_id": "my-app", "version": "0.0.0"},
        }
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(bundle))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_load_cache", lambda: {})
        monkeypatch.setattr(cli_main, "_save_cache", lambda _c: None)
        monkeypatch.setattr(cli_main, "_promote_profile_to_active", lambda _db, _tok: True)

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            if path == "/apps":
                return {"app_id": "app-uuid-1111"}
            if path == "/admin/profiles":
                return {"id": "db-uuid-2222"}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_login_register(
            SimpleNamespace(bundle_file=str(bundle_path), promote=True)
        )
        assert rc == 0
        persisted = json.loads(bundle_path.read_text())
        assert persisted["_provisioned"]["version_state"] == "ACTIVE"

    def test_without_flag_stays_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle = {
            "validation": {"generator_valid": True},
            "application_draft": {
                "name": "MyApp",
                "target_urls": ["https://example.com"],
                "login_config": {"credential_ref": "k8s:secret/tabby-my-app"},
            },
            "service_profile_draft": {"profile_id": "my-app", "version": "0.0.0"},
        }
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps(bundle))

        monkeypatch.setattr(cli_main, "_tabby_alive", lambda: True)
        monkeypatch.setattr(cli_main, "_get_admin_token", lambda: "tok")
        monkeypatch.setattr(cli_main, "_load_cache", lambda: {})
        monkeypatch.setattr(cli_main, "_save_cache", lambda _c: None)

        def _should_not_promote(*_a, **_k):  # pragma: no cover - regression guard
            raise AssertionError("register without --promote must not promote")

        monkeypatch.setattr(cli_main, "_promote_profile_to_active", _should_not_promote)

        def fake_http(method: str, path: str, body=None, token=None, timeout=15):  # noqa: ARG001
            if path == "/apps":
                return {"app_id": "app-uuid-1111"}
            if path == "/admin/profiles":
                return {"id": "db-uuid-2222"}
            raise AssertionError(f"unexpected call: {method} {path}")

        monkeypatch.setattr(cli_main, "_tabby_http", fake_http)

        rc = cli_main.cmd_login_register(
            SimpleNamespace(bundle_file=str(bundle_path), promote=False)
        )
        assert rc == 0
        persisted = json.loads(bundle_path.read_text())
        assert persisted["_provisioned"]["version_state"] == "STAGING"


# ---------------------------------------------------------------------------
# 7. Execute-readiness probe (gaps.md B4) — :9222 CDP vs :8091 execute
# ---------------------------------------------------------------------------


class TestProbeExecuteReady:
    """`_probe_execute_ready` classifies whether /execute/fetch actually works."""

    def test_dict_response_is_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli_main, "_tabby_http", lambda *a, **k: {"status": 200, "body": "ok"})
        state, _ = cli_main._probe_execute_ready("my-app", "tok")
        assert state == "ready"

    def test_no_healthy_session_404_is_no_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a, **_k):
            raise RuntimeError(
                'HTTP 404 from POST /execute/fetch: {"message":"No healthy session"}'
            )

        monkeypatch.setattr(cli_main, "_tabby_http", boom)
        state, _ = cli_main._probe_execute_ready("my-app", "tok")
        assert state == "no-route"

    def test_plain_404_is_no_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a, **_k):
            raise RuntimeError('HTTP 404 from POST /execute/fetch: {"message":"Cannot POST"}')

        monkeypatch.setattr(cli_main, "_tabby_http", boom)
        state, detail = cli_main._probe_execute_ready("my-app", "tok")
        assert state == "no-route"
        assert "not mounted" in detail

    def test_502_is_no_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a, **_k):
            raise RuntimeError("HTTP 502 from POST /execute/fetch: worker unreachable")

        monkeypatch.setattr(cli_main, "_tabby_http", boom)
        state, detail = cli_main._probe_execute_ready("my-app", "tok")
        assert state == "no-route"
        assert "LOCAL_WORKER_URL" in detail

    def test_unreachable_api_is_unknown_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a, **_k):
            raise RuntimeError("Cannot reach Tabby at http://localhost:8000 (Connection refused).")

        monkeypatch.setattr(cli_main, "_tabby_http", boom)
        state, _ = cli_main._probe_execute_ready("my-app", "tok")
        assert state == "unknown"


class TestReportExecuteReadiness:
    """`_report_execute_readiness` prints distinct CDP (:9222) and execute (:8091) lines."""

    def test_warns_when_execute_not_ready(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(cli_main, "_cdp_is_reachable", lambda *a, **k: True)
        monkeypatch.setattr(
            cli_main,
            "_probe_execute_ready",
            lambda _p, _t: ("no-route", "/execute/fetch returned 404 — execute routes not mounted"),
        )
        cli_main._report_execute_readiness("my-app", "tok")
        out = capsys.readouterr().out
        assert "CDP :9222" in out
        assert "Execute :8091" in out
        assert "NOT ready" in out
        assert "EXECUTE_ENABLED=true" in out

    def test_reports_ready(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(cli_main, "_cdp_is_reachable", lambda *a, **k: True)
        monkeypatch.setattr(cli_main, "_probe_execute_ready", lambda _p, _t: ("ready", "routed"))
        cli_main._report_execute_readiness("my-app", "tok")
        out = capsys.readouterr().out
        assert "Execute :8091" in out
        assert "ready" in out
        assert "NOT ready" not in out

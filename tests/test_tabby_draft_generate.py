"""Tests for compiler/login/tabby_draft_generator.py — generate() function."""

from __future__ import annotations

import json

import pytest

from compiler.login.tabby_draft_generator import (
    _analyze_har,
    build_app_template_payload,
    generate,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _session(
    app_name: str = "My App",
    login_url: str = "https://app.example.com/login",
    session_id: str = "sess-001",
) -> dict:
    return {"id": session_id, "app_name": app_name, "login_url": login_url}


def _click(
    event_type: str = "input",
    field_role: str = "username",
    field_name: str = "username",
    value: str = "alice",
    element_id: str = "username-input",
    tag_name: str = "input",
    input_type: str = "text",
) -> dict:
    return {
        "event_type": event_type,
        "field_role": field_role,
        "field_name": field_name,
        "value": value,
        "element_id": element_id,
        "tag_name": tag_name,
        "input_type": input_type,
        "selector": f"#{element_id}",
        "is_redacted": False,
        "data_attrs_json": None,
        "autocomplete": None,
        "aria_label": None,
        "placeholder": None,
    }


def _url_event(to_url: str, from_url: str = "") -> dict:
    return {"to_url": to_url, "from_url": from_url}


# ── generate() ───────────────────────────────────────────────────────────────


class TestGenerate:
    def test_returns_required_keys(self) -> None:
        result = generate(_session(), [], [])
        assert "recording" in result
        assert "application_draft" in result
        assert "service_profile_draft" in result
        assert "review_items" in result
        assert "validation" in result

    def test_recording_has_session_id(self) -> None:
        result = generate(_session(session_id="test-123"), [], [])
        assert result["recording"]["session_id"] == "test-123"

    def test_app_name_used(self) -> None:
        result = generate(_session(app_name="My Cool App"), [], [])
        app = result["application_draft"]
        assert "my-cool-app" in app.get("profile_id", "") or "My Cool App" in str(app)

    def _steps(self, result: dict) -> list[dict]:
        """Steps are in application_draft.login_config.steps."""
        return result["application_draft"]["login_config"]["steps"]

    def test_login_url_in_steps(self) -> None:
        result = generate(_session(login_url="https://app.example.com/login"), [], [])
        steps = self._steps(result)
        assert any(s.get("url") == "https://app.example.com/login" for s in steps)

    def test_no_login_url_uses_placeholder(self) -> None:
        session = {"id": "s1", "app_name": "App", "login_url": ""}
        result = generate(session, [], [])
        issues = result["validation"]["issues"]
        assert any("placeholder" in i.lower() for i in issues)

    def test_url_events_determine_first_url(self) -> None:
        session = {"id": "s1", "app_name": "App", "login_url": ""}
        url_events = [_url_event("https://observed.example.com/login")]
        result = generate(session, [], url_events)
        steps = self._steps(result)
        assert any("observed.example.com" in str(s) for s in steps)

    def test_username_fill_step_generated(self) -> None:
        clicks = [_click(event_type="input", field_role="username", value="alice")]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        fill_steps = [
            s for s in steps if s.get("action") == "fill" and s.get("value") == "${USERNAME}"
        ]
        assert len(fill_steps) >= 1

    def test_password_fill_step_generated(self) -> None:
        clicks = [
            _click(event_type="input", field_role="password", input_type="password", value="secret")
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        fill_steps = [
            s for s in steps if s.get("action") == "fill" and s.get("value") == "${PASSWORD}"
        ]
        assert len(fill_steps) >= 1

    def test_password_fill_has_sensitive_flag(self) -> None:
        clicks = [
            _click(event_type="input", field_role="password", input_type="password", value="s")
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        pw_steps = [s for s in steps if s.get("value") == "${PASSWORD}"]
        assert all(s.get("sensitive") is True for s in pw_steps)

    def test_click_step_generated(self) -> None:
        clicks = [
            {
                "event_type": "click",
                "field_role": "",
                "tag_name": "button",
                "input_type": "submit",
                "text_content": "Login",
                "selector": "button[type='submit']",
                "element_id": "",
                "field_name": "",
                "value": "",
                "is_redacted": False,
                "data_attrs_json": None,
                "autocomplete": None,
                "aria_label": None,
                "placeholder": None,
            }
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        click_steps = [s for s in steps if s.get("action") == "click"]
        assert len(click_steps) >= 1

    def test_otp_wait_for_step(self) -> None:
        clicks = [_click(event_type="input", field_role="otp", value="123456")]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        otp_steps = [s for s in steps if s.get("action") == "wait_for"]
        assert len(otp_steps) >= 1

    def test_low_confidence_produces_review_item(self) -> None:
        clicks = [
            {
                "event_type": "input",
                "field_role": "username",
                "tag_name": "input",
                "input_type": "text",
                "selector": "input",
                "element_id": "",
                "field_name": "",
                "value": "alice",
                "is_redacted": False,
                "data_attrs_json": None,
                "autocomplete": None,
                "aria_label": None,
                "placeholder": None,
            }
        ]
        result = generate(_session(), clicks, [])
        review = result["review_items"]
        assert any(r.get("type") == "selector_confidence" for r in review)

    def test_deduplication_of_consecutive_inputs(self) -> None:
        clicks = [
            _click(event_type="input", field_role="username", value="ali"),
            _click(event_type="input", field_role="username", value="alice"),
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        fill_steps = [s for s in steps if s.get("value") == "${USERNAME}"]
        assert len(fill_steps) == 1

    def test_field_role_inferred_from_input_type(self) -> None:
        clicks = [
            {
                "event_type": "input",
                "field_role": "",
                "tag_name": "input",
                "input_type": "password",
                "field_name": "",
                "element_id": "pwd",
                "value": "secret",
                "selector": "#pwd",
                "is_redacted": False,
                "data_attrs_json": None,
                "autocomplete": None,
                "aria_label": None,
                "placeholder": None,
            }
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        pw_steps = [s for s in steps if s.get("value") == "${PASSWORD}"]
        assert len(pw_steps) >= 1

    def test_field_role_inferred_from_email_field_name(self) -> None:
        clicks = [
            {
                "event_type": "input",
                "field_role": "",
                "tag_name": "input",
                "input_type": "text",
                "field_name": "email",
                "element_id": "email",
                "value": "alice@example.com",
                "selector": "#email",
                "is_redacted": False,
                "data_attrs_json": None,
                "autocomplete": None,
                "aria_label": None,
                "placeholder": None,
            }
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        user_steps = [s for s in steps if s.get("value") == "${USERNAME}"]
        assert len(user_steps) >= 1

    def test_select_step_generated(self) -> None:
        clicks = [
            {
                "event_type": "input",
                "field_role": "",
                "tag_name": "select",
                "input_type": "",
                "field_name": "region",
                "element_id": "region",
                "value": "us-east",
                "selector": "#region",
                "is_redacted": False,
                "data_attrs_json": None,
                "autocomplete": None,
                "aria_label": None,
                "placeholder": None,
            }
        ]
        result = generate(_session(), clicks, [])
        steps = self._steps(result)
        select_steps = [s for s in steps if s.get("action") == "select"]
        assert len(select_steps) >= 1

    def test_abcd_url_event_format(self) -> None:
        # Test abcd metadata_json format for URL events
        url_events = [
            {
                "to_url": "",
                "from_url": "",
                "metadata_json": json.dumps(
                    {"url": "https://app.example.com/dashboard", "from_url": ""}
                ),
            }
        ]
        # Should not crash
        result = generate(_session(), [], url_events)
        assert "service_profile_draft" in result

    def test_with_har_data(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://app.example.com/api/login",
                            "headers": [
                                {"name": "Set-Cookie", "value": "session=abc123"},
                                {"name": "Authorization", "value": "Bearer tok"},
                            ],
                        },
                        "response": {
                            "headers": [
                                {"name": "set-cookie", "value": "session=xyz; Path=/"},
                            ]
                        },
                    }
                ]
            }
        }
        result = generate(_session(), [], [], har=har)
        assert "service_profile_draft" in result

    def test_validation_generator_valid(self) -> None:
        result = generate(_session(), [], [])
        assert "generator_valid" in result["validation"]


# ── _analyze_har ──────────────────────────────────────────────────────────────


class TestAnalyzeHar:
    def test_none_returns_defaults(self) -> None:
        result = _analyze_har(None)
        assert result["has_cookies"] is False
        assert result["has_auth_headers"] is False
        assert result["has_csrf"] is False

    def test_set_cookie_detected(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {"url": "https://example.com/login", "headers": []},
                        "response": {
                            "headers": [{"name": "set-cookie", "value": "session=abc123; Path=/"}]
                        },
                    }
                ]
            }
        }
        result = _analyze_har(har)
        assert result["has_cookies"] is True
        assert "session" in result["set_cookie_headers"]

    def test_auth_header_detected(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://example.com/api",
                            "headers": [{"name": "Authorization", "value": "Bearer tok"}],
                        },
                        "response": {"headers": []},
                    }
                ]
            }
        }
        result = _analyze_har(har)
        assert result["has_auth_headers"] is True

    def test_csrf_header_detected(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://example.com/api",
                            "headers": [{"name": "X-CSRF-Token", "value": "abc"}],
                        },
                        "response": {"headers": []},
                    }
                ]
            }
        }
        result = _analyze_har(har)
        assert result["has_csrf"] is True

    def test_domains_collected(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {"url": "https://api.example.com/v1/data", "headers": []},
                        "response": {"headers": []},
                    }
                ]
            }
        }
        result = _analyze_har(har)
        assert "api.example.com" in result["auth_domains"]

    def test_empty_har(self) -> None:
        result = _analyze_har({"log": {"entries": []}})
        assert result["has_cookies"] is False
        assert result["auth_domains"] == []


# ── build_app_template_payload() (A1) ────────────────────────────────────────


class TestBuildAppTemplatePayload:
    """The App Template emitter payload derived from the generated drafts."""

    def _drafts(self) -> tuple[dict, dict]:
        result = generate(
            _session(app_name="My App", login_url="https://app.example.com/login"),
            [_click(field_role="username"), _click(field_role="password", input_type="password")],
            [_url_event("https://app.example.com/home")],
        )
        return result["application_draft"], result["service_profile_draft"]

    def test_pattern_equals_profile_slug(self) -> None:
        # CRITICAL invariant: profile_name_pattern MUST equal the runtime slug,
        # or autoProvisionFromTemplate never matches.
        app, prof = self._drafts()
        payload = build_app_template_payload(app, prof)
        assert payload["profile_name_pattern"] == prof["profile_id"]
        assert payload["profile_name_pattern"] == "my-app"

    def test_required_template_fields_present(self) -> None:
        app, prof = self._drafts()
        payload = build_app_template_payload(app, prof)
        for key in (
            "name",
            "profile_name_pattern",
            "login_config",
            "keepalive_config",
            "export_policy",
            "browser_policy",
            "notification_config",
        ):
            assert key in payload, f"template payload missing {key}"

    def test_credential_types_folded_into_export_policy(self) -> None:
        # autoProvisionFromTemplate clones credential_types from export_policy,
        # not from a profile draft — so they must be folded in.
        app, prof = self._drafts()
        prof = {
            **prof,
            "credential_types": {
                "cookies": [{"name": "sid", "volatility": "STABLE"}],
                "headers": [],
            },
            "target_domains": ["app.example.com"],
        }
        payload = build_app_template_payload(app, prof)
        assert payload["export_policy"]["credential_types"] == prof["credential_types"]
        assert payload["export_policy"]["target_domains"] == ["app.example.com"]

    def test_execute_enabled_true_by_default(self) -> None:
        app, prof = self._drafts()
        payload = build_app_template_payload(app, prof)
        assert payload["execute_enabled"] is True

    def test_execute_enabled_mirrors_app_draft(self) -> None:
        app, prof = self._drafts()
        app = {**app, "execute_enabled": False}
        payload = build_app_template_payload(app, prof)
        assert payload["execute_enabled"] is False

    def test_missing_profile_id_raises(self) -> None:
        app, prof = self._drafts()
        prof = {k: v for k, v in prof.items() if k != "profile_id"}
        with pytest.raises(ValueError, match="profile_id"):
            build_app_template_payload(app, prof)

    def test_browser_policy_defaults_when_absent(self) -> None:
        app, prof = self._drafts()
        payload = build_app_template_payload(app, prof)
        # app draft has no browser_policy → safe default, not None.
        assert payload["browser_policy"] == {
            "clipboard": False,
            "downloads": False,
            "file_chooser": False,
        }

"""Tests for Tabby-routed REST emission in the WDL exporter."""

from __future__ import annotations

from backend.elicitation.profile_generator import generate_adopt_profile
from backend.elicitation.wdl_generator import generate_wdl


def _auth_har_entry() -> dict:
    """A HAR entry on an authenticated host (Bearer token present)."""
    return {
        "request": {
            "method": "GET",
            "url": "https://api.secure.example.com/v1/orders",
            "headers": [
                {"name": "Authorization", "value": "Bearer abc123def456ghi789"},
            ],
        },
        "response": {"status": 200, "content": {"text": ""}},
        "startedDateTime": "2024-01-01T00:00:00Z",
    }


def _first_rest_step(result: dict) -> dict:
    return next(s for s in result["steps"] if s["operation"] == "REST")


def test_rest_step_routed_through_tabby_when_profile_and_auth_host():
    result = generate_wdl(
        har_entries=[_auth_har_entry()],
        profile_slug="my-profile",
    )
    step = _first_rest_step(result)
    assert step["via"] == "tabby"
    assert step["tabby_profile_id"] == "my-profile"


def test_rest_step_unchanged_without_profile_slug():
    result = generate_wdl(har_entries=[_auth_har_entry()])
    step = _first_rest_step(result)
    assert "via" not in step
    assert "tabby_profile_id" not in step


def test_rest_step_unchanged_for_non_auth_host():
    # No auth indicators -> host is not an auth domain -> plain REST step.
    entry = _auth_har_entry()
    entry["request"]["headers"] = []
    result = generate_wdl(har_entries=[entry], profile_slug="my-profile")
    step = _first_rest_step(result)
    assert "via" not in step
    assert "tabby_profile_id" not in step


def test_adopt_profile_sets_top_level_tabby_profile_id():
    profile = generate_adopt_profile(
        base_url="https://api.secure.example.com",
        har_entries=[_auth_har_entry()],
        profile_slug="my-profile",
    )
    assert profile["tabby_profile_id"] == "my-profile"


def test_adopt_profile_omits_tabby_profile_id_when_absent():
    profile = generate_adopt_profile(
        base_url="https://api.secure.example.com",
        har_entries=[_auth_har_entry()],
    )
    assert "tabby_profile_id" not in profile

"""Tests for Tabby-routed REST emission in the WDL exporter.

Routing rule: when a profile_slug is supplied, a REST step is routed through
Tabby (`via:"tabby"` + `tabby_profile_id`) when its host is EITHER first-party to
the recorded site (same registrable domain as base_url) OR carries a detected
auth indicator. First-party routing covers cookie-authenticated / anti-bot
domains (e.g. Akamai) that expose no Authorization header.
"""

from __future__ import annotations

from backend.elicitation.profile_generator import generate_adopt_profile
from backend.elicitation.wdl_generator import generate_wdl


def _entry(url: str, headers: list[dict] | None = None) -> dict:
    return {
        "request": {"method": "GET", "url": url, "headers": headers or []},
        "response": {"status": 200, "content": {"text": ""}},
        "startedDateTime": "2024-01-01T00:00:00Z",
    }


def _bearer_entry() -> dict:
    return _entry(
        "https://api.secure.example.com/v1/orders",
        [{"name": "Authorization", "value": "Bearer abc123def456ghi789"}],
    )


def _rest_steps(result: dict) -> list[dict]:
    return [s for s in result["steps"] if s["operation"] == "REST"]


def _step_for(result: dict, needle: str) -> dict:
    return next(s for s in _rest_steps(result) if needle in s["config"]["url"])


def test_first_party_cookie_host_routed_even_without_auth_header():
    # The recorded site authenticates via cookies (no Authorization header) —
    # the anti-bot case. It must still be routed through Tabby.
    entry = _entry(
        "https://www.expedia.com/api/search?q=nyc", [{"name": "Cookie", "value": "sess=abc"}]
    )
    result = generate_wdl(
        har_entries=[entry], base_url="https://www.expedia.com/", profile_slug="exp"
    )
    step = _rest_steps(result)[0]
    assert step.get("via") == "tabby"
    assert step.get("tabby_profile_id") == "exp"


def test_subdomain_of_recorded_site_is_first_party():
    entry = _entry("https://api.expedia.com/graphql", [])
    result = generate_wdl(
        har_entries=[entry], base_url="https://www.expedia.com/", profile_slug="exp"
    )
    assert _rest_steps(result)[0].get("via") == "tabby"


def test_third_party_non_auth_host_not_routed():
    result = generate_wdl(
        har_entries=[
            _entry(
                "https://www.expedia.com/api/search?q=nyc", [{"name": "Cookie", "value": "s=1"}]
            ),
            _entry("https://analytics.tracker.com/collect?id=1", []),
        ],
        base_url="https://www.expedia.com/",
        profile_slug="exp",
    )
    assert _step_for(result, "{{base_url}}").get("via") == "tabby"  # first-party
    assert "via" not in _step_for(result, "tracker.com")  # third-party, no auth


def test_auth_host_routed_even_when_third_party():
    # A Bearer-token host that is NOT the recorded site is still routed via auth detection.
    result = generate_wdl(
        har_entries=[_bearer_entry()], base_url="https://app.other-site.com/", profile_slug="p"
    )
    assert _rest_steps(result)[0].get("via") == "tabby"


def test_rest_step_unchanged_without_profile_slug():
    result = generate_wdl(har_entries=[_bearer_entry()])
    step = _rest_steps(result)[0]
    assert "via" not in step and "tabby_profile_id" not in step


def test_adopt_profile_sets_top_level_tabby_profile_id():
    profile = generate_adopt_profile(
        base_url="https://api.secure.example.com",
        har_entries=[_bearer_entry()],
        profile_slug="my-profile",
    )
    assert profile["tabby_profile_id"] == "my-profile"


def test_adopt_profile_omits_tabby_profile_id_when_absent():
    profile = generate_adopt_profile(
        base_url="https://api.secure.example.com", har_entries=[_bearer_entry()]
    )
    assert "tabby_profile_id" not in profile

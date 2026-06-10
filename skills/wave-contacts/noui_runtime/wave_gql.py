"""Wave GraphQL runtime — Tabby-routed calls against gql.waveapps.com/graphql/public.

Requests run via Tabby's POST /execute/fetch, i.e. ``fetch()`` executed inside the
authenticated Wave browser session. The session's own auth (cookies + the SPA's
in-page fetch wrapper) is applied by the browser, so no Bearer token is sniffed
or passed from Python.
"""

from __future__ import annotations

import base64
import json
import os

from .execute import execute_fetch

GQL_URL = "https://gql.waveapps.com/graphql/public"


def _profile_id() -> str:
    return os.environ.get("PROFILE_SLUG") or "wave"


def _url_uuid_to_gql_id(uuid: str) -> str:
    """Convert a URL business UUID to Wave's GraphQL business id (base64 Business:uuid)."""
    if uuid.startswith("Qn") or len(uuid) > 36:
        return uuid
    return base64.b64encode(f"Business:{uuid}".encode()).decode()


async def gql_request(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL operation inside the authenticated Wave browser session.

    Returns the parsed JSON body (``data`` + optional ``errors``).
    """
    body = await execute_fetch(
        _profile_id(),
        GQL_URL,
        method="POST",
        body={"query": query, "variables": variables or {}},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    if not isinstance(body, dict):
        raise RuntimeError(f"Unexpected GraphQL response: {str(body)[:300]}")
    if body.get("errors") and not body.get("data"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'])[:300]}")
    return body


async def get_business_id() -> str:
    """Resolve the Wave business GraphQL id (env override, else first businesses query)."""
    env = os.environ.get("WAVE_BUSINESS_ID")
    if env:
        return _url_uuid_to_gql_id(env.strip())

    res = await gql_request(
        "query { businesses(page: 1, pageSize: 5) { edges { node { id name } } } }"
    )
    edges = (((res.get("data") or {}).get("businesses") or {}).get("edges")) or []
    if not edges:
        raise RuntimeError(
            "Could not resolve Wave business id. Open app.waveapps.com/businesses/<id>/... "
            "in the Tabby session or set WAVE_BUSINESS_ID."
        )
    return edges[0]["node"]["id"]


def gql_input_errors(body: dict, key: str) -> None:
    """Raise if a Wave mutation returned didSucceed=false with inputErrors."""
    payload = (body.get("data") or {}).get(key) or {}
    if payload.get("didSucceed") is False:
        errs = payload.get("inputErrors") or body.get("errors") or []
        raise RuntimeError(f"Wave mutation failed: {json.dumps(errs)[:300]}")

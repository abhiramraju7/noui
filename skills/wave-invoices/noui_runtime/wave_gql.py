"""Wave GraphQL runtime — CDP-backed calls against gql.waveapps.com/graphql/public."""

from __future__ import annotations

import base64
import json
import os
import re

import httpx

from .cdp import cdp_eval, find_page
from .wave_auth import get_bearer

GQL_URL = "https://gql.waveapps.com/graphql/public"
PAGE_MATCH = "waveapps.com"


def _url_uuid_to_gql_id(uuid: str) -> str:
    """Convert a URL business UUID to Wave's GraphQL business id (base64 Business:uuid)."""
    if uuid.startswith("Qn") or len(uuid) > 36:
        return uuid
    return base64.b64encode(f"Business:{uuid}".encode()).decode()


async def _find_page_ws() -> str | None:
    return await find_page(PAGE_MATCH)


async def get_business_id() -> str:
    """Resolve the Wave business GraphQL id (env, URL, or first businesses query)."""
    env = os.environ.get("WAVE_BUSINESS_ID")
    if env:
        return _url_uuid_to_gql_id(env.strip())

    ws_url = await _find_page_ws()
    if ws_url:
        async with httpx.AsyncClient() as client:
            targets = (await client.get("http://localhost:9222/json", timeout=5)).json()
        for t in targets:
            if t.get("type") == "page" and PAGE_MATCH in t.get("url", ""):
                url = t.get("url", "")
                m = re.search(r"/businesses/([0-9a-f-]{36})", url, re.I)
                if m:
                    return _url_uuid_to_gql_id(m.group(1))

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


async def gql_request(
    query: str,
    variables: dict | None = None,
    *,
    force_bearer: bool = False,
) -> dict:
    """POST a GraphQL operation inside the authenticated browser.

    Returns the parsed JSON body (``data`` + optional ``errors``). Retries once
    with a fresh bearer on 401/403.
    """
    ws_url = await _find_page_ws()
    if not ws_url:
        raise RuntimeError(
            f"No Tabby page matching {PAGE_MATCH!r}. Run `tabby session ensure --profile wave`."
        )

    async def _run(bearer: str) -> dict:
        init = {
            "method": "POST",
            "credentials": "omit",
            "headers": {
                "Authorization": bearer,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            "body": json.dumps({"query": query, "variables": variables or {}}),
        }
        js = (
            f"fetch({json.dumps(GQL_URL)}, {json.dumps(init)}).then("
            "r => r.text().then(t => JSON.stringify({status: r.status, body: t})))"
        )
        return await cdp_eval(ws_url, js)

    bearer = await get_bearer(force=force_bearer)
    res = await _run(bearer)
    if res.get("status") in (401, 403):
        res = await _run(await get_bearer(force=True))

    status = res.get("status")
    try:
        body = json.loads(res.get("body", "") or "{}")
    except (ValueError, TypeError):
        body = {"errors": [{"message": str(res.get("body", ""))[:300]}]}

    if status not in (200, 201):
        raise RuntimeError(f"GraphQL HTTP {status}: {str(body)[:300]}")
    if body.get("errors") and not body.get("data"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'])[:300]}")
    return body


def gql_input_errors(body: dict, key: str) -> None:
    """Raise if a Wave mutation returned didSucceed=false with inputErrors."""
    payload = (body.get("data") or {}).get(key) or {}
    if payload.get("didSucceed") is False:
        errs = payload.get("inputErrors") or body.get("errors") or []
        raise RuntimeError(f"Wave mutation failed: {json.dumps(errs)[:300]}")

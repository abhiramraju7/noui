"""In-memory command queue for browser <-> backend communication.

Commands are created by MCP tool handlers and consumed by the Chrome extension
via polling. Results flow back through asyncio.Event synchronization.

When TABBY_API_URL, TABBY_CLIENT_ID, and TABBY_PROFILE_ID are set, commands
are routed to Tabby's POST /execute/browser endpoint instead — no extension needed.
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Tabby driver configuration
# ---------------------------------------------------------------------------

_agent_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


def _use_tabby_driver() -> bool:
    return bool(
        os.environ.get("TABBY_API_URL")
        and os.environ.get("TABBY_CLIENT_ID")
        and os.environ.get("TABBY_PROFILE_ID")
    )


async def _get_agent_token() -> str:
    """Exchange client credentials for an agent bearer token, with caching."""
    now = time.time()
    if _agent_token_cache["token"] and _agent_token_cache["expires_at"] > now + 30:
        return _agent_token_cache["token"]

    api_host = os.environ["TABBY_API_URL"].rstrip("/")
    client_id = os.environ["TABBY_CLIENT_ID"]
    client_secret = os.environ["TABBY_CLIENT_SECRET"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_host}/auth/agent-token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    token = data.get("access_token") or data.get("token", "")
    if not token:
        raise RuntimeError(f"POST /auth/agent-token returned no token: {data}")

    # Cache for ~50 minutes (agent tokens default to 1 hour TTL)
    _agent_token_cache["token"] = token
    _agent_token_cache["expires_at"] = now + 3000

    return token


async def _execute_command_via_tabby(command_type: str, params: dict) -> dict:
    """Execute a browser command via Tabby's POST /execute/browser endpoint.

    Returns the same {success, data, error} shape as the extension driver.
    """
    api_host = os.environ["TABBY_API_URL"].rstrip("/")
    profile_id = os.environ["TABBY_PROFILE_ID"]
    token = await _get_agent_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_host}/execute/browser",
            json={
                "profile_id": profile_id,
                "command": command_type,
                "params": params,
                "timeout_ms": COMMAND_TIMEOUT_SECONDS * 1000,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=COMMAND_TIMEOUT_SECONDS + 5,
        )

    if resp.status_code == 409:
        raise RuntimeError(
            f"Tabby session conflict: {resp.text}. Another consumer may be driving this session."
        )
    if resp.status_code == 429:
        raise RuntimeError(f"Rate limited by Tabby: {resp.text}")
    if resp.status_code >= 400:
        raise RuntimeError(f"Tabby execute/browser failed ({resp.status_code}): {resp.text[:500]}")

    return resp.json()


# ---------------------------------------------------------------------------
# Extension driver (original queue-based approach)
# ---------------------------------------------------------------------------


@dataclass
class BrowserCommand:
    """A command queued for the Chrome extension to execute."""

    id: str
    command_type: str
    params: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: dict | None = None


# Commands waiting to be picked up by the extension
_pending: dict[str, BrowserCommand] = {}

# Commands currently being executed by the extension
_active: dict[str, BrowserCommand] = {}


def create_command(command_type: str, params: dict) -> BrowserCommand:
    cmd = BrowserCommand(
        id=str(uuid.uuid4()),
        command_type=command_type,
        params=params,
    )
    _pending[cmd.id] = cmd
    logger.info("Browser command created: %s (%s)", cmd.id, command_type)
    return cmd


def get_pending_commands() -> list[BrowserCommand]:
    """Get all pending commands and move them to active."""
    if not _pending:
        return []
    commands = list(_pending.values())
    for cmd in commands:
        _pending.pop(cmd.id)
        _active[cmd.id] = cmd
    return commands


def set_result(cmd_id: str, result: dict) -> bool:
    """Set the result for an active command and signal the waiting MCP tool."""
    cmd = _active.pop(cmd_id, None)
    if cmd is None:
        logger.warning("set_result called for unknown command: %s", cmd_id)
        return False
    cmd.result = result
    cmd.event.set()
    logger.info("Browser command result set: %s", cmd_id)
    return True


async def _execute_command_via_extension(command_type: str, params: dict) -> dict:
    """Create a command, wait for the extension to execute it, return the result."""
    cmd = create_command(command_type, params)
    try:
        await asyncio.wait_for(cmd.event.wait(), timeout=COMMAND_TIMEOUT_SECONDS)
    except TimeoutError:
        _pending.pop(cmd.id, None)
        _active.pop(cmd.id, None)
        raise TimeoutError(
            f"Browser command '{command_type}' timed out after {COMMAND_TIMEOUT_SECONDS}s. "
            "Is the Chrome extension running and connected?"
        ) from None
    assert cmd.result is not None
    return cmd.result


# ---------------------------------------------------------------------------
# Public API — routes to Tabby or extension based on environment
# ---------------------------------------------------------------------------


async def execute_command(command_type: str, params: dict) -> dict:
    """Execute a browser command, routing to Tabby or the extension.

    When TABBY_API_URL, TABBY_CLIENT_ID, and TABBY_PROFILE_ID are set,
    commands go to Tabby's POST /execute/browser. Otherwise, they go to
    the Chrome extension via the in-memory queue.

    Raises:
        TimeoutError: If the extension does not respond within COMMAND_TIMEOUT_SECONDS.
        RuntimeError: If the Tabby driver encounters an error.
    """
    if _use_tabby_driver():
        logger.debug("Routing command '%s' via Tabby driver", command_type)
        return await _execute_command_via_tabby(command_type, params)

    logger.debug("Routing command '%s' via extension driver", command_type)
    return await _execute_command_via_extension(command_type, params)

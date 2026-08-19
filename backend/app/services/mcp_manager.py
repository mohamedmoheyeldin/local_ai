from __future__ import annotations

import json
import os
import shlex
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from .credential_vault import vault


def _headers(server: dict[str, Any]) -> dict[str, str]:
    public = server.get("public_config", {})
    secrets = server.get("secrets", {})
    auth = server.get("auth_type")
    headers: dict[str, str] = {}
    if auth == "bearer" and secrets.get("access_token"):
        headers["Authorization"] = f"Bearer {secrets['access_token']}"
    elif auth == "api-key" and secrets.get("api_key"):
        headers[public.get("header_name", "X-API-Key")] = secrets["api_key"]
    elif auth == "basic" and secrets.get("password"):
        import base64
        encoded = base64.b64encode(f"{public.get('username', '')}:{secrets['password']}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    elif auth == "custom-headers":
        names = [item.strip() for item in public.get("header_names", "").split(",") if item.strip()]
        values = [item.strip() for item in secrets.get("header_values", "").split(",")]
        headers.update(dict(zip(names, values)))
    elif auth == "session-cookie" and secrets.get("cookie_value"):
        headers["Cookie"] = f"{public.get('cookie_name', 'session')}={secrets['cookie_value']}"
    oauth = secrets.get("oauth_tokens")
    if isinstance(oauth, dict) and oauth.get("access_token"):
        headers["Authorization"] = f"Bearer {oauth['access_token']}"
    return headers


@asynccontextmanager
async def connected_client(server: dict[str, Any]) -> AsyncIterator[Client]:
    oauth = server.get("secrets", {}).get("oauth_tokens")
    if isinstance(oauth, dict) and oauth.get("refresh_token") and int(oauth.get("expires_at", 0)) <= int(time.time()) + 60:
        token_endpoint = server.get("public_config", {}).get("token_endpoint")
        client_id = server.get("public_config", {}).get("client_id")
        if token_endpoint and client_id:
            data = {"grant_type": "refresh_token", "refresh_token": oauth["refresh_token"], "client_id": client_id}
            if server.get("secrets", {}).get("client_secret"):
                data["client_secret"] = server["secrets"]["client_secret"]
            async with httpx2.AsyncClient(timeout=20) as refresh_client:
                response = await refresh_client.post(token_endpoint, data=data)
                response.raise_for_status()
                refreshed = response.json()
            refreshed.setdefault("refresh_token", oauth["refresh_token"])
            refreshed["obtained_at"] = int(time.time())
            refreshed["expires_at"] = int(time.time()) + int(refreshed.get("expires_in", 3600))
            server["secrets"]["oauth_tokens"] = refreshed
            vault.set_json(f"mcp:{server['id']}", server["secrets"])
    transport = server["transport"]
    if transport == "stdio":
        env = os.environ.copy()
        if server.get("auth_type") == "environment":
            for line in server.get("secrets", {}).get("environment", "").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip():
                        env[key.strip()] = value
        parameters = StdioServerParameters(
            command=server["command"],
            args=shlex.split(server.get("arguments", "")),
            cwd=str(Path(server["working_directory"]).expanduser()) if server.get("working_directory") else None,
            env=env,
        )
        async with stdio_client(parameters) as streams:
            async with Client(streams, read_timeout_seconds=20) as client:
                yield client
        return
    if transport == "streamable-http":
        async with httpx2.AsyncClient(headers=_headers(server), timeout=20) as http_client:
            async with streamable_http_client(server["endpoint"], http_client=http_client) as streams:
                async with Client(streams, read_timeout_seconds=20) as client:
                    yield client
        return
    if transport == "sse-legacy":
        # Client's URL auto-detection preserves compatibility with older SSE servers.
        async with Client(server["endpoint"], read_timeout_seconds=20) as client:
            yield client
        return
    raise ValueError("Custom MCP transport cannot be started automatically")


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return json.loads(json.dumps(value, default=str))


async def discover(server: dict[str, Any]) -> dict[str, Any]:
    async with connected_client(server) as client:
        tools = await client.list_tools()
        try:
            resources = await client.list_resources()
        except Exception:
            resources = None
        try:
            prompts = await client.list_prompts()
        except Exception:
            prompts = None
    return {
        "tools": [_dump(item) for item in tools.tools],
        "resources": [_dump(item) for item in resources.resources] if resources else [],
        "prompts": [_dump(item) for item in prompts.prompts] if prompts else [],
    }


async def call(server: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with connected_client(server) as client:
        result = await client.call_tool(tool_name, arguments)
    return _dump(result)

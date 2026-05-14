#!/usr/bin/env python3
"""
Salesforce MCP Server - SSE transport with per-user credentials via HTTP headers.

Each user passes their Salesforce credentials through HTTP headers:
  X-SF-USERNAME, X-SF-PASSWORD, X-SF-SECURITY-TOKEN, X-SF-LOGIN-URL

The ASGI middleware injects these into env vars before each request.
"""
import os

# Load .env file (server defaults)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Import the MCP server module (loads all tools)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mcp_server",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-server.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SFCredentialsMiddleware:
    """Raw ASGI middleware - injects per-user SF creds from HTTP headers."""
    HEADER_MAP = {
        b"x-sf-username":       "SF_USERNAME",
        b"x-sf-password":       "SF_PASSWORD",
        b"x-sf-security-token": "SF_SECURITY_TOKEN",
        b"x-sf-login-url":      "SF_LOGIN_URL",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            old_values = {}
            for header_key, env_key in self.HEADER_MAP.items():
                value = headers.get(header_key, b"").decode("utf-8", errors="replace")
                if value:
                    old_values[env_key] = os.environ.get(env_key)
                    os.environ[env_key] = value
            try:
                await self.app(scope, receive, send)
            finally:
                for env_key, old_val in old_values.items():
                    if old_val is None:
                        os.environ.pop(env_key, None)
                    else:
                        os.environ[env_key] = old_val
        else:
            await self.app(scope, receive, send)


# Build the ASGI app
port = int(os.environ.get("MCP_PORT", "8765"))
print(f"[salesforce-mcp] Starting SSE server on port {port}...", flush=True)
print(f"[salesforce-mcp] Supports per-user credentials via X-SF-* headers", flush=True)

import uvicorn
sse_app = mod.mcp.sse_app()
app = SFCredentialsMiddleware(sse_app)
uvicorn.run(app, host="0.0.0.0", port=port)

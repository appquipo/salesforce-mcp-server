#!/usr/bin/env python3
"""Wrapper to run Salesforce MCP Server with SSE transport for remote hosting."""
import os

# Load .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

# Import the MCP server module (loads all tools)
import importlib.util
spec = importlib.util.spec_from_file_location("mcp_server", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Run with SSE transport
port = int(os.environ.get("MCP_PORT", "8765"))
print(f"[salesforce-mcp] Starting SSE server on port {port}...", flush=True)

import uvicorn
app = mod.mcp.sse_app()
uvicorn.run(app, host="0.0.0.0", port=port)

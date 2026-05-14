# Odoo CRM MCP Server for Claude

Connect your Odoo CRM to Claude - search leads, manage your pipeline, create opportunities, log activities, and more through natural conversation.

**Live endpoint:** `https://mcp-social-crm.ezxdemo.com/odoo/sse`

> Looking for the Salesforce server? Switch to the [`salesforce` branch](https://github.com/appquipo/salesforce-mcp-server/tree/salesforce).

## Quick Start

### Option 1: Install the Cowork Plugin

1. Download `odoo-crm-remote.plugin` from the [latest release](https://github.com/appquipo/salesforce-mcp-server/releases/latest)
2. Double-click to install in Claude Desktop / Cowork
3. Open a new chat and say: **"I want to connect my Odoo CRM"**
4. Claude will ask for your Odoo URL, database, and credentials

### Option 2: Manual .mcp.json Setup

Add this to your `.mcp.json` (Claude Code or Cowork plugin):

```json
{
  "mcpServers": {
    "odoo-crm": {
      "type": "sse",
      "url": "https://mcp-social-crm.ezxdemo.com/odoo/sse",
      "headers": {
        "X-ODOO-URL": "${ODOO_URL}",
        "X-ODOO-DB": "${ODOO_DB}",
        "X-ODOO-USERNAME": "${ODOO_USERNAME}",
        "X-ODOO-PASSWORD": "${ODOO_PASSWORD}",
        "X-ODOO-API-KEY": "${ODOO_API_KEY}"
      }
    }
  }
}
```

Then set environment variables:

```bash
export ODOO_URL="https://your-company.odoo.com"
export ODOO_DB="your-database-name"
export ODOO_USERNAME="your-email@example.com"
export ODOO_PASSWORD="your-password"
export ODOO_API_KEY=""  # Optional: use API key instead of password
```

**How to find your Database Name:** Check your Odoo URL or go to Settings > Database in your Odoo instance.

## Available Tools

| Tool | Description |
|------|-------------|
| `odoo_test_connection` | Verify Odoo credentials |
| `odoo_search_leads` | Search leads/opportunities with filters |
| `odoo_get_lead` | Get lead details by ID |
| `odoo_create_lead` | Create a new lead |
| `odoo_update_lead` | Update lead fields |
| `odoo_get_pipeline_stages` | List pipeline stages |
| `odoo_convert_to_opportunity` | Convert lead to opportunity |
| `odoo_create_activity` | Schedule an activity |
| `odoo_get_activities` | Get activities for a lead |
| `odoo_log_note` | Log a note on a lead |
| `odoo_search_contacts` | Search contacts/partners |
| `odoo_get_lead_messages` | Get lead message history |

## Architecture

```
Claude (Cowork/Claude Code)
    |
    | SSE + X-ODOO-* headers
    v
nginx (mcp-social-crm.ezxdemo.com/odoo/)
    |
    | proxy_pass :8766
    v
run-http.py (FastMCP + Uvicorn)
    |  OdooCredentialsMiddleware extracts headers -> env vars
    v
Odoo JSON-RPC API (17+)
```

Per-user credentials are passed via HTTP headers on every SSE connection. No credentials are stored on the server.

## Self-Hosting

```bash
# Clone
git clone -b odoo-crm https://github.com/appquipo/salesforce-mcp-server.git odoo-crm-mcp
cd odoo-crm-mcp

# Install
pip install mcp uvicorn

# Run
python3 run-http.py
# Listening on port 8766
```

### Requirements

- Python 3.8+
- `mcp>=1.0.0`, `uvicorn>=0.30.0`
- Odoo 17+ instance with JSON-RPC API access

## Troubleshooting

- **421 Misdirected Request**: The server uses `enable_dns_rebinding_protection=False` because it runs behind an nginx reverse proxy.
- **Authentication failed**: Verify your Odoo URL, database name, and credentials. Try logging into the Odoo web UI with the same credentials.
- **API key vs password**: You can use either. Set `ODOO_API_KEY` for key-based auth, or `ODOO_PASSWORD` for password auth.

## License

MIT

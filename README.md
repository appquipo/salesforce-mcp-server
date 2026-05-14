# Salesforce MCP Server for Claude

Connect your Salesforce CRM to Claude - search, create, and manage leads, contacts, accounts, and opportunities through natural conversation.

**Live endpoint:** `https://mcp-social-crm.ezxdemo.com/salesforce/sse`

> Looking for the Odoo CRM server? Switch to the [`odoo-crm` branch](https://github.com/appquipo/salesforce-mcp-server/tree/odoo-crm).

## Quick Start

### Option 1: Install the Cowork Plugin

1. Download `salesforce-crm.plugin` from the [latest release](https://github.com/appquipo/salesforce-mcp-server/releases/latest)
2. Double-click to install in Claude Desktop / Cowork
3. Open a new chat and say: **"I want to connect my Salesforce account"**
4. Claude will ask for your credentials and handle the rest

### Option 2: Manual .mcp.json Setup

Add this to your `.mcp.json` (Claude Code or Cowork plugin):

```json
{
  "mcpServers": {
    "salesforce-crm": {
      "type": "sse",
      "url": "https://mcp-social-crm.ezxdemo.com/salesforce/sse",
      "headers": {
        "X-SF-USERNAME": "${SF_USERNAME}",
        "X-SF-PASSWORD": "${SF_PASSWORD}",
        "X-SF-SECURITY-TOKEN": "${SF_SECURITY_TOKEN}",
        "X-SF-LOGIN-URL": "${SF_LOGIN_URL}"
      }
    }
  }
}
```

Then set environment variables:

```bash
export SF_USERNAME="your-salesforce-email@example.com"
export SF_PASSWORD="your-salesforce-password"
export SF_SECURITY_TOKEN="your-security-token"
export SF_LOGIN_URL="https://login.salesforce.com"
```

**How to get your Security Token:** In Salesforce, go to Settings > My Personal Information > Reset My Security Token. The token is emailed to you.

## Available Tools

| Tool | Description |
|------|-------------|
| `sf_search_leads` | Search leads with filters |
| `sf_get_lead` | Get lead by ID |
| `sf_create_lead` | Create a new lead |
| `sf_update_lead` | Update lead fields |
| `sf_search_contacts` | Search contacts |
| `sf_search_accounts` | Search accounts |
| `sf_search_opportunities` | Search opportunities |
| `sf_create_opportunity` | Create opportunity |
| `sf_soql_query` | Run custom SOQL queries |
| `sf_describe_object` | Describe object schema |
| `sf_create_task` | Create a task |
| `sf_log_call` | Log a call activity |

## Architecture

```
Claude (Cowork/Claude Code)
    |
    | SSE + X-SF-* headers
    v
nginx (mcp-social-crm.ezxdemo.com/salesforce/)
    |
    | proxy_pass :8765
    v
run-http.py (FastMCP + Uvicorn)
    |  SFCredentialsMiddleware extracts headers -> env vars
    v
mcp-server.py (12 Salesforce tools)
    |
    | simple_salesforce
    v
Salesforce REST API
```

Per-user credentials are passed via HTTP headers on every SSE connection. No credentials are stored on the server.

## Self-Hosting

To host your own instance:

```bash
# Clone and install
git clone https://github.com/appquipo/salesforce-mcp-server.git
cd salesforce-mcp-server
pip install mcp uvicorn simple_salesforce

# Configure defaults (optional)
cp .env.example .env
# Edit .env with your Salesforce credentials

# Run
python3 run-http.py
# Listening on port 8765
```

### Requirements

- Python 3.8+
- `mcp>=1.0.0`, `uvicorn>=0.30.0`, `simple_salesforce`

## Troubleshooting

- **421 Misdirected Request**: The server uses `enable_dns_rebinding_protection=False` in `TransportSecuritySettings` because it runs behind an nginx reverse proxy.
- **Credentials not working**: Make sure your Security Token is current. Reset it from Salesforce Settings if needed.
- **macOS GUI apps**: If using Claude Desktop (not terminal), you may need to set env vars via a LaunchAgent plist so the GUI app picks them up.

## License

MIT

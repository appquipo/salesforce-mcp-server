# Salesforce CRM MCP Server

A single-file PHP MCP server that connects any Salesforce org to AI assistants via the Model Context Protocol (MCP).

**Works with:** Claude Desktop (Cowork), Claude Code, and any MCP-compatible client.

## Features

- **13 tools** covering Leads, Contacts, Accounts, Opportunities, Tasks, Users, and raw SOQL
- **Dual auth** — Username/Password/Token OR OAuth 2.0 Client Credentials
- **Zero dependencies** — single PHP file, no Composer, no frameworks
- **Any Salesforce org** — Production, Sandbox, Developer Edition
- **Streamable HTTP transport** — MCP protocol version 2025-03-26

## Quick Start

### 1. Deploy the server

Upload `mcp.php` to any PHP 8.0+ web server with cURL enabled.

```
your-server.com/mcp.php
```

### 2. Configure credentials

Set environment variables on your server. Choose ONE auth method:

#### Option A: Username + Password + Security Token

```bash
export SF_USERNAME="you@company.com"
export SF_PASSWORD="YourPassword"
export SF_SECURITY_TOKEN="YourSecurityToken"
```

To find your Security Token: Salesforce > Settings > My Personal Information > Reset My Security Token.

#### Option B: OAuth 2.0 (Connected App)

```bash
export SF_CLIENT_ID="your_connected_app_client_id"
export SF_CLIENT_SECRET="your_connected_app_client_secret"
export SF_LOGIN_URL="https://login.salesforce.com"
```

**Creating a Connected App:**
1. Salesforce Setup > App Manager > New Connected App
2. Enable OAuth Settings
3. Select scope: `full` or `api`
4. Enable Client Credentials Flow
5. Assign a Run As user
6. Copy Consumer Key (Client ID) and Consumer Secret (Client Secret)

#### Optional settings

```bash
export SF_LOGIN_URL="https://test.salesforce.com"   # Use for Sandbox orgs
export SF_API_VERSION="v62.0"                        # Default: v62.0
export SF_INSTANCE_URL="https://yourinstance.my.salesforce.com"  # Required for OAuth
```

### 3. Verify setup

```
GET https://your-server.com/mcp.php?setup
```

Returns:
```json
{
  "auth_configured": true,
  "auth_method": "password",
  "salesforce_connected": true,
  "instance_url": "https://yourinstance.my.salesforce.com"
}
```

### 4. Connect to your MCP client

#### Claude Desktop / Cowork

Create a plugin with this `.mcp.json`:

```json
{
  "mcpServers": {
    "salesforce": {
      "type": "http",
      "url": "https://your-server.com/mcp.php"
    }
  }
}
```

#### Claude Code

Add to your Claude Code settings:

```json
{
  "mcpServers": {
    "salesforce": {
      "type": "http",
      "url": "https://your-server.com/mcp.php"
    }
  }
}
```

## Available Tools

### Leads
| Tool | Description |
|------|-------------|
| `sf_search_leads` | Search leads by name, email, company, or phone |
| `sf_get_lead` | Get full details of a lead by ID |
| `sf_create_lead` | Create a new lead with any valid fields |
| `sf_update_lead` | Update fields on an existing lead |
| `sf_delete_lead` | Permanently delete a lead |
| `sf_change_owner` | Change lead owner to a different user |

### Activities
| Tool | Description |
|------|-------------|
| `sf_log_activity` | Log a task/activity on a lead (call, email, note) |

### Search
| Tool | Description |
|------|-------------|
| `sf_search_contacts` | Search contacts by name or email |
| `sf_search_accounts` | Search accounts by name |
| `sf_search_opportunities` | Search opportunities by name or account |
| `sf_search_users` | Search active Salesforce users (for owner assignment) |

### Schema & Query
| Tool | Description |
|------|-------------|
| `sf_describe_object` | List all fields on any Salesforce object |
| `sf_soql_query` | Run read-only SOQL queries |

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SF_USERNAME` | Auth A | Salesforce username |
| `SF_PASSWORD` | Auth A | Salesforce password |
| `SF_SECURITY_TOKEN` | Auth A | Salesforce security token |
| `SF_CLIENT_ID` | Auth B | OAuth Connected App Client ID |
| `SF_CLIENT_SECRET` | Auth B | OAuth Connected App Client Secret |
| `SF_LOGIN_URL` | No | Login URL (default: `https://login.salesforce.com`, use `https://test.salesforce.com` for Sandbox) |
| `SF_INSTANCE_URL` | OAuth | Your Salesforce instance URL |
| `SF_API_VERSION` | No | API version (default: `v62.0`) |

## Server Requirements

- PHP 8.0 or higher
- cURL extension enabled
- Write access to system temp directory (for session cache)
- HTTPS recommended for production

## Security Notes

- Never commit credentials to version control
- Use environment variables or `.env` files for configuration
- The server caches Salesforce sessions for 90 minutes in the system temp directory
- SOQL query tool only allows SELECT statements
- All user inputs are sanitized before SOQL queries

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/mcp.php` | MCP JSON-RPC endpoint |
| `GET` | `/mcp.php?health` | Health check |
| `GET` | `/mcp.php?setup` | Setup verification |
| `GET` | `/mcp.php` | Server info |

## License

MIT License - free for personal and commercial use.

## Credits

Built by [Emizentech](https://www.emizentech.com) - AI & CRM Development Services.

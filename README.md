# Salesforce MCP Server for Claude

Connect your Salesforce CRM to Claude — search, create, and manage leads, contacts, accounts, and opportunities through natural conversation.

## Quick Start (Plug & Play — Recommended)

**No setup required.** Connect to the hosted MCP server instantly.

### Option 1: Install the Plugin (Easiest)

1. Download [salesforce-crm.plugin](https://github.com/appquipo/salesforce-mcp-server/releases/latest/download/salesforce-crm.plugin)
2. Double-click to install in Claude Desktop / Cowork
3. Done! Start chatting with your Salesforce data

### Option 2: Add to Claude Code

Run in your terminal:

```bash
claude mcp add salesforce --url https://mcp-social-crm.ezxdemo.com/sse
```

### Option 3: Manual MCP Config

Add this to your `.mcp.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "salesforce": {
      "url": "https://mcp-social-crm.ezxdemo.com/sse"
    }
  }
}
```

That's it — no Python, no dependencies, no API keys to configure.

---

## Available Tools (13 Tools)

### Lead Management
| Tool | Description |
|------|-------------|
| `sf_search_leads` | Search leads by name, email, company, or phone |
| `sf_get_lead` | Get full lead details by ID |
| `sf_create_lead` | Create a new lead (LastName & Company required) |
| `sf_update_lead` | Update fields on an existing lead |
| `sf_delete_lead` | Permanently delete a lead |
| `sf_change_owner` | Reassign lead to a different owner |

### Activities
| Tool | Description |
|------|-------------|
| `sf_log_activity` | Log calls, emails, meetings, or notes on a lead |

### CRM Search
| Tool | Description |
|------|-------------|
| `sf_search_contacts` | Find contacts by name or email |
| `sf_search_accounts` | Find accounts by name |
| `sf_search_opportunities` | Find opportunities by name or account |
| `sf_search_users` | Find Salesforce users (for owner assignment) |

### Schema & Query
| Tool | Description |
|------|-------------|
| `sf_describe_object` | List all fields on any Salesforce object |
| `sf_soql_query` | Run read-only SOQL SELECT queries |

---

## Example Usage

Once connected, just chat naturally with Claude:

- "Search for leads named John"
- "Show me all opportunities over $50,000"
- "Create a new lead: Jane Smith at Acme Corp, email jane@acme.com"
- "Log a call with lead 00Qxx... — discussed pricing, follow up next week"
- "What custom fields are on the Lead object?"
- "Run SOQL: SELECT Name, Amount FROM Opportunity WHERE StageName = 'Closed Won'"

---

## Self-Hosting (Advanced)

Want to run your own server? Two options:

### Python Server (SSE Transport)

Requires Python 3.10+

```bash
# 1. Clone the repo
git clone https://github.com/appquipo/salesforce-mcp-server.git
cd salesforce-mcp-server

# 2. Install dependencies
pip install pydantic "mcp[cli]" uvicorn

# 3. Create .env with your Salesforce credentials
cat > .env << EOF
SF_USERNAME=your-username@example.com
SF_PASSWORD=your-password
SF_SECURITY_TOKEN=your-security-token
SF_LOGIN_URL=https://login.salesforce.com
MCP_PORT=8765
EOF

# 4. Start the server
python3 run-http.py
```

The server runs on port 8765. Point your MCP config to `http://your-server:8765/sse`.

**Nginx reverse proxy example:**

```nginx
location /sse {
    proxy_pass http://127.0.0.1:8765/sse;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400;
}

location /messages/ {
    proxy_pass http://127.0.0.1:8765/messages/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_buffering off;
}
```

### PHP Server (Streamable HTTP)

Requires PHP 8.0+ — just drop `mcp.php` on any web server.

```bash
# 1. Copy mcp.php to your web root
cp mcp.php /var/www/html/

# 2. Set environment variables in .env
SF_USERNAME=your-username@example.com
SF_PASSWORD=your-password
SF_SECURITY_TOKEN=your-security-token
MCP_API_KEY=your-secret-api-key

# 3. Point your MCP config to the URL
```

```json
{
  "mcpServers": {
    "salesforce": {
      "url": "https://your-domain.com/mcp.php",
      "headers": {
        "Authorization": "Bearer your-secret-api-key"
      }
    }
  }
}
```

### Local Mode (Stdio Transport)

Run directly on your machine without a server:

```bash
# 1. Clone and install
git clone https://github.com/appquipo/salesforce-mcp-server.git
pip install pydantic "mcp[cli]"

# 2. Use this .mcp.json
```

```json
{
  "mcpServers": {
    "salesforce": {
      "command": "python3",
      "args": ["path/to/mcp-server.py"],
      "env": {
        "SF_USERNAME": "your-username@example.com",
        "SF_PASSWORD": "your-password",
        "SF_SECURITY_TOKEN": "your-security-token",
        "SF_LOGIN_URL": "https://login.salesforce.com"
      }
    }
  }
}
```

---

## Salesforce Auth Methods

### 1. Username + Password + Security Token (Default)

Set these environment variables:
- `SF_USERNAME` — Your Salesforce username
- `SF_PASSWORD` — Your Salesforce password
- `SF_SECURITY_TOKEN` — Your security token ([how to get it](https://help.salesforce.com/s/articleView?id=sf.user_security_token.htm))
- `SF_LOGIN_URL` — `https://login.salesforce.com` (production) or `https://test.salesforce.com` (sandbox)

### 2. OAuth 2.0 Client Credentials (Connected App)

Set these instead:
- `SF_CLIENT_ID` — Connected App consumer key
- `SF_CLIENT_SECRET` — Connected App consumer secret
- `SF_LOGIN_URL` — Your Salesforce login URL

---

## Cowork Plugin Installation

For Claude Desktop Cowork mode:

```bash
claude plugin install https://github.com/appquipo/salesforce-mcp-server
```

Or download `salesforce-crm.plugin` from [Releases](https://github.com/appquipo/salesforce-mcp-server/releases) and double-click to install.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Built by [Appquipo](https://github.com/appquipo) / [Emizentech](https://emizentech.com)

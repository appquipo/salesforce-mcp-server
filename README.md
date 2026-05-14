# Salesforce MCP Server for Claude

Connect your Salesforce CRM to Claude — search, create, and manage leads, contacts, accounts, and opportunities through natural conversation.

## Quick Start (Plug & Play)

### Step 1: Install the Plugin

1. Download `salesforce-crm.plugin` from the [latest release](https://github.com/appquipo/salesforce-mcp-server/releases/latest)
2. Double-click the downloaded file to install in Claude Desktop / Cowork

### Step 2: Set Up Your Salesforce Credentials

**No terminal or coding required!** Just start a new chat in Claude and say:

> "I want to connect my Salesforce account"

Claude will walk you through it step by step:
1. Ask for your **Salesforce username** (your login email)
2. Ask for your **Salesforce password**
3. Ask for your **Security Token** — Claude will explain how to get it from Salesforce
4. Ask for your **Login URL** — usually `https://login.salesforce.com`

Claude will then generate a one-click setup script that configures everything automatically. Just double-click the script, restart Claude, and you're connected!

> **How to get your Security Token:** In Salesforce, click your profile icon → Settings → search "Reset My Security Token" → click Reset. The token will be emailed to you.

> **Sandbox orgs:** Use `https://test.salesforce.com` as the Login URL.

### Step 3: Start Using It

After restarting Claude, just chat naturally:

- "Search for leads named John"
- "Show me all opportunities over $50,000"
- "Create a new lead: Jane Smith at Acme Corp"
- "Log a call with lead — discussed pricing, follow up next week"

---

## What's Included

| Category | Tools | Description |
|----------|-------|-------------|
| **Lead Management** | `sf_search_leads`, `sf_get_lead`, `sf_create_lead`, `sf_update_lead`, `sf_delete_lead`, `sf_change_owner` | Full lead CRUD + ownership |
| **Activities** | `sf_log_activity` | Log calls, emails, meetings, notes |
| **CRM Search** | `sf_search_contacts`, `sf_search_accounts`, `sf_search_opportunities`, `sf_search_users` | Search across all CRM objects |
| **Schema & Query** | `sf_describe_object`, `sf_soql_query` | Explore fields, run SOQL queries |

---

## Alternative Setup Methods

### Add to Claude Code

```bash
claude mcp add salesforce --url https://mcp-social-crm.ezxdemo.com/sse
```

### Manual MCP Config

Add this to your `.mcp.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "salesforce": {
      "type": "sse",
      "url": "https://mcp-social-crm.ezxdemo.com/sse",
      "headers": {
        "X-SF-Username": "${SF_USERNAME}",
        "X-SF-Password": "${SF_PASSWORD}",
        "X-SF-Security-Token": "${SF_SECURITY_TOKEN}",
        "X-SF-Login-URL": "${SF_LOGIN_URL}"
      }
    }
  }
}
```

### Manual Environment Variables (Advanced)

If you prefer to set credentials manually:

**Mac/Linux** — add to `~/.zshrc` or `~/.bashrc`:
```bash
export SF_USERNAME="your-salesforce-email@example.com"
export SF_PASSWORD="your-salesforce-password"
export SF_SECURITY_TOKEN="your-security-token"
export SF_LOGIN_URL="https://login.salesforce.com"
```
Then run `source ~/.zshrc` and restart Claude.

**Windows** — set via System Properties > Environment Variables, then restart Claude.

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

The server runs on port 8765 and supports per-user credentials via `X-SF-*` HTTP headers.

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

### Local Mode (Stdio Transport)

Run directly on your machine without a server — see the repo files for configuration examples.

---

## Salesforce Auth

### Username + Password + Security Token (Default)
- `SF_USERNAME` — Your Salesforce username
- `SF_PASSWORD` — Your Salesforce password
- `SF_SECURITY_TOKEN` — Your security token ([how to get it](https://help.salesforce.com/s/articleView?id=sf.user_security_token.htm))
- `SF_LOGIN_URL` — `https://login.salesforce.com` (production) or `https://test.salesforce.com` (sandbox)

### OAuth 2.0 Client Credentials (Connected App)
- `SF_CLIENT_ID` — Connected App consumer key
- `SF_CLIENT_SECRET` — Connected App consumer secret
- `SF_LOGIN_URL` — Your Salesforce login URL

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Built by [Appquipo](https://appquipo.com) / [Emizentech](https://emizentech.com)

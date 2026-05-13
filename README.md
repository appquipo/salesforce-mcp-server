# Salesforce MCP Server for Claude

Connect your Salesforce CRM to Claude — search, create, and manage leads, contacts, accounts, and opportunities through natural conversation.

## Quick Start (Plug & Play)

### Step 1: Install the Plugin

1. Download [salesforce-crm.plugin](https://github.com/appquipo/salesforce-mcp-server/releases/latest/download/salesforce-crm.plugin)
2. Double-click to install in Claude Desktop / Cowork

### Step 2: Set Up Your Salesforce Credentials

The plugin connects to a hosted MCP server. You need to provide your own Salesforce credentials as environment variables.

**Mac/Linux** — add these to your `~/.zshrc` (or `~/.bashrc`):

```bash
export SF_USERNAME="your-salesforce-email@example.com"
export SF_PASSWORD="your-salesforce-password"
export SF_SECURITY_TOKEN="your-security-token"
export SF_LOGIN_URL="https://login.salesforce.com"
```

Then run:

```bash
source ~/.zshrc
```

**Windows** — set via System Properties > Environment Variables:

- `SF_USERNAME` = your Salesforce login email
- `SF_PASSWORD` = your Salesforce password
- `SF_SECURITY_TOKEN` = your security token
- `SF_LOGIN_URL` = `https://login.salesforce.com`

> **How to get your Security Token:** In Salesforce, go to Settings > My Personal Information > Reset My Security Token. The token will be emailed to you.

> **Sandbox orgs:** Use `https://test.salesforce.com` for SF_LOGIN_URL.

### Step 3: Restart Claude

After setting the environment variables, **restart Claude Desktop / Cowork** and start chatting with your Salesforce data!

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

---

## Available Tools (13 Tools)

### Lead Management

| Tool | Description |
|------|-------------|
| sf_search_leads | Search leads by name, email, company, or phone |
| sf_get_lead | Get full lead details by ID |
| sf_create_lead | Create a new lead (LastName & Company required) |
| sf_update_lead | Update fields on an existing lead |
| sf_delete_lead | Permanently delete a lead |
| sf_change_owner | Reassign lead to a different owner |

### Activities

| Tool | Description |
|------|-------------|
| sf_log_activity | Log calls, emails, meetings, or notes on a lead |

### CRM Search

| Tool | Description |
|------|-------------|
| sf_search_contacts | Find contacts by name or email |
| sf_search_accounts | Find accounts by name |
| sf_search_opportunities | Find opportunities by name or account |
| sf_search_users | Find Salesforce users (for owner assignment) |

### Schema & Query

| Tool | Description |
|------|-------------|
| sf_describe_object | List all fields on any Salesforce object |
| sf_soql_query | Run read-only SOQL SELECT queries |

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

The server runs on port 8765 and supports per-user credentials via `X-SF-*` HTTP headers. Point your MCP config to `http://your-server:8765/sse`.

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

**Built by [Appquipo](https://appquipo.com) / [Emizentech](https://emizentech.com)**

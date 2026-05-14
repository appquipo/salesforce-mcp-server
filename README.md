# Salesforce MCP Server for Claude

Connect your Salesforce CRM to Claude — search, create, and manage leads, contacts, accounts, and opportunities through natural conversation.

## Quick Start

### 1. Install the Plugin

- Download `salesforce-crm.plugin` from the [latest release](https://github.com/appquipo/salesforce-mcp-server/releases/latest)
- Double-click to install in Claude Desktop / Cowork

### 2. Connect Your Salesforce Account

Open a new chat in Claude and say:

> **"I want to connect my Salesforce account"**

Claude will ask for your credentials one at a time:

1. **Your Salesforce email** (the one you use to log in)
2. **Your Salesforce password**
3. **Your Security Token** — Claude will show you exactly how to get this from Salesforce
4. Claude handles everything else automatically

### 3. Restart Claude

After Claude sets things up, just **quit Claude (Cmd+Q)** and reopen it. That's it — you're connected!

> **Tip:** If it doesn't connect after restarting, try restarting your Mac once. On some setups, a full reboot is needed for the credentials to take effect.

---

## What You Can Do

Once connected, just chat naturally:

- "Search for leads named John"
- "Create a new lead: Jane Smith at Acme Corp, email jane@acme.com"
- "Show me all opportunities over $50,000"
- "Log a call with the lead — discussed pricing, follow up next week"
- "What custom fields are on the Lead object?"
- "Run SOQL: SELECT Name, Amount FROM Opportunity WHERE StageName = 'Closed Won'"

### All 13 Tools

| Category | Tools |
|----------|-------|
| **Leads** | Search, view, create, update, delete, reassign leads |
| **Activities** | Log calls, emails, meetings, notes |
| **CRM Search** | Search contacts, accounts, opportunities, users |
| **Advanced** | Explore object fields, run SOQL queries |

---

## Troubleshooting

**"Couldn't reach the MCP server"**
- Make sure you fully quit Claude with **Cmd+Q** (not just close the window) and reopened it
- Try restarting your Mac — this ensures the credentials are loaded for all apps
- If your company uses a custom Salesforce URL (like `https://yourcompany.my.salesforce.com`), tell Claude and it will update the connection

**"Tools not showing up"**
- Go to Claude → Settings → Plugins and check that Salesforce is enabled
- Try toggling it off and back on, then restart Claude

---

## Alternative Setup Methods

### Claude Code

```bash
claude mcp add salesforce --url https://mcp-social-crm.ezxdemo.com/sse
```

### Manual MCP Config

Add to your `.mcp.json` or Claude Desktop config:

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

> **macOS note:** Claude Desktop is a GUI app and does NOT read `~/.zshrc`. You must set environment variables using `launchctl setenv` or a LaunchAgents plist. The plugin handles this automatically when you say "connect my Salesforce account".

---

## Self-Hosting (Advanced)

Want to run your own server?

### Python Server (SSE Transport)

Requires Python 3.10+

```bash
git clone https://github.com/appquipo/salesforce-mcp-server.git
cd salesforce-mcp-server
pip install pydantic "mcp[cli]" uvicorn

cat > .env << EOF
SF_USERNAME=your-username@example.com
SF_PASSWORD=your-password
SF_SECURITY_TOKEN=your-security-token
SF_LOGIN_URL=https://login.salesforce.com
MCP_PORT=8765
EOF

python3 run-http.py
```

The server supports per-user credentials via `X-SF-*` HTTP headers.

**Nginx reverse proxy:**
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

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Built by [Appquipo](https://appquipo.com) / [Emizentech](https://emizentech.com)

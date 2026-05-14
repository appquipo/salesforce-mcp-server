# Odoo CRM Plugin for Claude

Connect your Odoo CRM to Claude. No coding required. Works with any Odoo 17+ instance.

## How to Use

### 1. Download & Install

Download **[odoo-crm-remote.plugin](./odoo-crm-remote.plugin)** and double-click to install in Claude.

### 2. Connect Your Account

Open a new chat in Claude and say:

> **"I want to connect my Odoo CRM"**

Claude will ask for your login details one by one:
- Your Odoo URL (e.g., https://mycompany.odoo.com)
- Your database name
- Your email/username
- Your password

Claude handles everything else automatically. No terminal, no code.

### 3. Restart Claude

After Claude sets things up, just **quit Claude (Cmd+Q)** and reopen it. Done!

## What You Can Do

Just chat naturally:
- "Show me my recent leads"
- "Create a new lead for Sarah at TechCorp"
- "What are my pipeline stages?"
- "Schedule a follow-up call with the Acme lead"
- "Log a note on the Dyson opportunity"

## Troubleshooting

- **Not connecting?** Make sure you restarted Claude after setup. On some Macs, a full reboot helps.
- **Wrong credentials?** Say "I want to reconnect my Odoo CRM" and Claude will update your details.
- **Database name?** It usually matches your Odoo subdomain (e.g., if URL is https://myco.odoo.com, database is "myco").

---

> Also available: [Salesforce CRM Plugin](https://github.com/appquipo/salesforce-mcp-server/tree/salesforce)

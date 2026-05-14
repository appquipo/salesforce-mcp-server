# Odoo CRM Plugin for Claude

Connect your Odoo CRM to Claude in 3 simple steps. No coding required. Works with any Odoo 17+ instance.

## Setup (3 minutes)

### Step 1: Download & Install

Download **[odoo-crm-remote.plugin](./odoo-crm-remote.plugin)** and double-click it to install in Claude.

### Step 2: Set Your Login Details

Open **Terminal** (Mac) or **PowerShell** (Windows) and paste these commands with your own Odoo credentials:

**Mac:**
```bash
echo 'export ODOO_URL="https://your-company.odoo.com"' >> ~/.zshrc
echo 'export ODOO_DB="your-database-name"' >> ~/.zshrc
echo 'export ODOO_USERNAME="your-email@example.com"' >> ~/.zshrc
echo 'export ODOO_PASSWORD="your-password"' >> ~/.zshrc
echo 'export ODOO_API_KEY=""' >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell as Admin):**
```powershell
[System.Environment]::SetEnvironmentVariable("ODOO_URL", "https://your-company.odoo.com", "User")
[System.Environment]::SetEnvironmentVariable("ODOO_DB", "your-database-name", "User")
[System.Environment]::SetEnvironmentVariable("ODOO_USERNAME", "your-email@example.com", "User")
[System.Environment]::SetEnvironmentVariable("ODOO_PASSWORD", "your-password", "User")
[System.Environment]::SetEnvironmentVariable("ODOO_API_KEY", "", "User")
```

**How to find your Database Name:**
- Check your Odoo URL (the subdomain is usually the database name)
- Or in Odoo: Settings > Database

**API Key (optional):** If you prefer API key instead of password:
- In Odoo: Settings > Users > your user > Preferences > API Keys
- Click "New API Key", copy it, and put it in ODOO_API_KEY

### Step 3: Restart Claude

Quit Claude completely (Cmd+Q on Mac, close on Windows) and reopen it. That\'s it!

## Try It

Open a new chat and say:
- "Show me my recent leads"
- "Create a new lead for Sarah at TechCorp"
- "What are my pipeline stages?"
- "Schedule a call with the Acme lead for tomorrow"

## What You Can Do

| Command | What it does |
|---------|-------------|
| Search leads | Find leads by name, company, or stage |
| Create leads | Add new leads with contact info |
| Update leads | Change stage, priority, or details |
| Pipeline stages | See all your pipeline stages |
| Convert to opportunity | Move a lead to opportunity |
| Schedule activities | Plan calls, meetings, emails, to-dos |
| Log notes | Add notes to any lead |
| Search contacts | Find contacts and partners |
| Message history | See all messages on a lead |

## Troubleshooting

**"Authentication failed"** - Double-check your Odoo URL, database name, username, and password. Try logging into Odoo web with the same credentials.

**"Tools not available"** - Make sure you restarted Claude after setting your credentials.

**API Key vs Password** - You can use either one. If using API key, set it in ODOO_API_KEY and leave ODOO_PASSWORD empty.

---

> Also available: [Salesforce CRM Plugin](https://github.com/appquipo/salesforce-mcp-server/tree/salesforce)

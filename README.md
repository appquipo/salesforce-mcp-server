# Salesforce CRM Plugin for Claude

Connect your Salesforce CRM to Claude in 3 simple steps. No coding required.

## Setup (3 minutes)

### Step 1: Download & Install

Download **[salesforce-crm.plugin](./salesforce-crm.plugin)** and double-click it to install in Claude.

### Step 2: Set Your Login Details

Open **Terminal** (Mac) or **PowerShell** (Windows) and paste these commands with your own Salesforce credentials:

**Mac:**
```bash
echo 'export SF_USERNAME="your-salesforce-email@example.com"' >> ~/.zshrc
echo 'export SF_PASSWORD="your-salesforce-password"' >> ~/.zshrc
echo 'export SF_SECURITY_TOKEN="your-security-token"' >> ~/.zshrc
echo 'export SF_LOGIN_URL="https://login.salesforce.com"' >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell as Admin):**
```powershell
[System.Environment]::SetEnvironmentVariable("SF_USERNAME", "your-salesforce-email@example.com", "User")
[System.Environment]::SetEnvironmentVariable("SF_PASSWORD", "your-salesforce-password", "User")
[System.Environment]::SetEnvironmentVariable("SF_SECURITY_TOKEN", "your-security-token", "User")
[System.Environment]::SetEnvironmentVariable("SF_LOGIN_URL", "https://login.salesforce.com", "User")
```

**How to get your Security Token:**
1. Log into Salesforce
2. Click your profile icon (top right) > **Settings**
3. Left sidebar: **My Personal Information** > **Reset My Security Token**
4. Click "Reset Security Token" - check your email for the token

### Step 3: Restart Claude

Quit Claude completely (Cmd+Q on Mac, close on Windows) and reopen it. That\'s it!

## Try It

Open a new chat and say:
- "Show me my recent leads"
- "Create a new lead for John Smith at Acme Corp"
- "Search for opportunities closing this month"
- "Log a call with the marketing team"

## What You Can Do

| Command | What it does |
|---------|-------------|
| Search leads | Find leads by name, company, email, or status |
| Create leads | Add new leads with contact info |
| Update leads | Change lead status, score, or details |
| Search contacts | Find contacts across your org |
| Search accounts | Look up account information |
| Search opportunities | Check your pipeline and deals |
| Run SOQL queries | Custom Salesforce queries |
| Log calls & tasks | Record activities on records |

## Troubleshooting

**"Authentication failed"** - Double-check your username, password, and security token. Reset your token from Salesforce Settings if needed.

**"Tools not available"** - Make sure you restarted Claude after setting your credentials. On Mac, sometimes a full reboot is needed.

**Sandbox account?** - Change your login URL to `https://test.salesforce.com`

---

> Also available: [Odoo CRM Plugin](https://github.com/appquipo/salesforce-mcp-server/tree/odoo-crm)

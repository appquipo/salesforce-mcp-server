# MCP CRM Servers for Claude

Production-ready MCP servers that connect Claude AI to your CRM via SSE (Server-Sent Events). Per-user credentials via HTTP headers - no credentials stored on the server.

**Live at:** `https://mcp-social-crm.ezxdemo.com`

## Available Servers

| CRM | Branch | Endpoint | Plugin |
|-----|--------|----------|--------|
| **Salesforce** | [`salesforce`](https://github.com/appquipo/salesforce-mcp-server/tree/salesforce) | `/salesforce/sse` | `salesforce-crm.plugin` |
| **Odoo CRM** | [`odoo-crm`](https://github.com/appquipo/salesforce-mcp-server/tree/odoo-crm) | `/odoo/sse` | `odoo-crm-remote.plugin` |

## Quick Start

Pick your CRM and switch to its branch for full setup instructions:

### Salesforce

```bash
git clone -b salesforce https://github.com/appquipo/salesforce-mcp-server.git
```

Or add to your `.mcp.json`:

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

### Odoo CRM

```bash
git clone -b odoo-crm https://github.com/appquipo/salesforce-mcp-server.git
```

Or add to your `.mcp.json`:

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

## Architecture

Both servers share the same domain with subfolder routing:

```
mcp-social-crm.ezxdemo.com (nginx + SSL)
    |
    +-- /salesforce/*  -->  port 8765 (Salesforce MCP)
    |
    +-- /odoo/*        -->  port 8766 (Odoo CRM MCP)
```

Each server uses FastMCP with SSE transport and ASGI middleware that reads per-user credentials from HTTP headers. See the individual branch READMEs for details.

## License

MIT

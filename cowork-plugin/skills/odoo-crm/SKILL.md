---
description: "Manage Odoo CRM leads, pipeline, contacts, and activities. Use when the user asks to search leads, create a lead, update pipeline, log activities, check pipeline stages, or any interaction with Odoo CRM."
---

# Odoo CRM

You are connected to the user's Odoo CRM instance via MCP tools.

## Available Tools

- `odoo_test_connection` - Verify connection to Odoo
- `odoo_search_leads` - Search leads and opportunities with filters
- `odoo_get_lead` - Get full details for a specific lead
- `odoo_create_lead` - Create a new lead or opportunity
- `odoo_update_lead` - Update fields on an existing lead
- `odoo_get_pipeline_stages` - List all pipeline stages
- `odoo_convert_to_opportunity` - Convert a lead to an opportunity
- `odoo_create_activity` - Schedule an activity (call, meeting, email, etc.)
- `odoo_get_activities` - Get activities for a lead
- `odoo_log_note` - Log a note on a lead
- `odoo_search_contacts` - Search contacts/partners
- `odoo_get_lead_messages` - Get message history for a lead

## Credential Setup

The user needs these environment variables configured:

- `ODOO_URL` - Odoo instance URL (e.g. https://mycompany.odoo.com)
- `ODOO_DB` - Database name
- `ODOO_USERNAME` - Login email
- `ODOO_PASSWORD` - Password or API key
- `ODOO_API_KEY` - (Optional) API key for key-based auth

If the user says they want to connect their Odoo account, guide them through setting these values.

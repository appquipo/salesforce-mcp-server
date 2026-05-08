---
name: salesforce-crm
description: "Manage Salesforce CRM leads, contacts, accounts, and opportunities. Search records, create and update leads, log activities, run SOQL queries, and explore object schemas. Use when the user asks to search leads, create a lead, update Salesforce, log a call, check pipeline, run a SOQL query, or describe Salesforce fields."
---

# Salesforce CRM

This skill provides guidance for working with the Salesforce CRM MCP server.

## Available Tools

### Lead Management
- **sf_search_leads** — Search leads by name, email, company, or phone
- **sf_get_lead** — Get full lead details by ID
- **sf_create_lead** — Create a new lead (pass any valid fields)
- **sf_update_lead** — Update fields on an existing lead
- **sf_delete_lead** — Permanently delete a lead
- **sf_change_owner** — Reassign lead ownership

### Activities
- **sf_log_activity** — Log calls, emails, meetings, or notes on a lead

### CRM Search
- **sf_search_contacts** — Find contacts by name or email
- **sf_search_accounts** — Find accounts by name
- **sf_search_opportunities** — Find opportunities by name or account
- **sf_search_users** — Find Salesforce users (for owner assignment)

### Schema & Query
- **sf_describe_object** — List all fields on any Salesforce object (Lead, Contact, Account, etc.)
- **sf_soql_query** — Run read-only SOQL SELECT queries

## Best Practices

1. **Always search before creating** — check if a lead/contact already exists
2. **Use sf_describe_object** to discover custom fields in the user's Salesforce org before creating or updating records
3. **Never change lead owner** without explicit user permission
4. **Use sf_soql_query** for complex searches that the dedicated search tools can't handle
5. **Log activities** after any significant interaction with a lead

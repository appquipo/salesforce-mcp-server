#!/usr/bin/env python3
"""
Odoo CRM MCP Server — SSE transport with server-side credential storage.

Credentials can be provided in two ways:
  1. HTTP headers (X-ODOO-URL, X-ODOO-DB, etc.) — backward compatible
  2. The odoo_configure tool — stores credentials on the server, no env vars needed

The odoo_configure approach means users only need to enter credentials once
through chat. No Terminal, no environment variables, no scripts.

Run:
    pip install mcp uvicorn
    uvicorn run-http:app --host 0.0.0.0 --port 8766
"""

import json
import os
import urllib.request
import urllib.error
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "odoo-crm",
    host="0.0.0.0",
    port=8766,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# ---------------------------------------------------------------------------
# Server-side credential storage
# ---------------------------------------------------------------------------

CREDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials_store.json")

# In-memory credential store: { email: { url, db, username, password, api_key } }
_cred_store: dict[str, dict] = {}

# Track which user is "active" (set by last odoo_configure call)
_active_user: dict[str, str] = {"email": ""}


def _load_creds_from_disk():
    """Load stored credentials from disk on startup."""
    global _cred_store
    try:
        with open(CREDS_FILE) as f:
            _cred_store = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cred_store = {}


def _save_creds_to_disk():
    """Persist credentials to disk."""
    try:
        with open(CREDS_FILE, "w") as f:
            json.dump(_cred_store, f, indent=2)
    except OSError:
        pass  # Non-fatal: credentials still in memory


# Load on import
_load_creds_from_disk()

# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

_uid_cache: dict[str, int] = {}
_req_id = 0


def _next_id() -> int:
    global _req_id
    _req_id += 1
    return _req_id


def _get_creds() -> dict:
    """Get Odoo credentials. Priority: env vars (from headers) > active user > single stored user."""
    # 1. Check env vars (set by header middleware — backward compatible)
    url = os.environ.get("ODOO_URL", "").rstrip("/")
    if url:
        return {
            "url": url,
            "db": os.environ.get("ODOO_DB", ""),
            "username": os.environ.get("ODOO_USERNAME", ""),
            "password": os.environ.get("ODOO_PASSWORD", ""),
            "api_key": os.environ.get("ODOO_API_KEY", ""),
        }

    # 2. Check active user (set by most recent odoo_configure call)
    active = _active_user.get("email", "")
    if active and active in _cred_store:
        return dict(_cred_store[active])

    # 3. If exactly one user is stored, use that
    if len(_cred_store) == 1:
        return dict(list(_cred_store.values())[0])

    # 4. If multiple users stored but none active
    if len(_cred_store) > 1:
        users = ", ".join(_cred_store.keys())
        raise RuntimeError(
            f"Multiple Odoo accounts configured ({users}). "
            "Please call odoo_configure with your credentials to select your account."
        )

    # 5. No credentials at all
    raise RuntimeError(
        "Odoo CRM is not configured yet. "
        "Please use the odoo_configure tool with your Odoo URL, database, username, and password."
    )


def _jsonrpc(url: str, method: str, params: dict) -> Any:
    """Send a JSON-RPC 2.0 request and return the result."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _next_id(),
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Odoo connection failed: {exc}") from exc

    if "error" in body:
        err = body["error"]
        msg = err.get("data", {}).get("message", err.get("message", str(err)))
        raise RuntimeError(f"Odoo RPC error: {msg}")
    return body.get("result")


def _authenticate() -> int:
    """Authenticate with Odoo and return the user ID."""
    creds = _get_creds()

    if not creds["url"]:
        raise RuntimeError("Odoo URL not configured — use odoo_configure to set up")

    cache_key = f"{creds['url']}|{creds['username']}"
    if cache_key in _uid_cache:
        return _uid_cache[cache_key]

    password = creds["api_key"] or creds["password"]
    if not password:
        raise RuntimeError("No password or API key configured")
    if not creds["db"]:
        raise RuntimeError("Database name not configured")
    if not creds["username"]:
        raise RuntimeError("Username not configured")

    result = _jsonrpc(
        f"{creds['url']}/jsonrpc",
        "call",
        {
            "service": "common",
            "method": "authenticate",
            "args": [creds["db"], creds["username"], password, {}],
        },
    )
    if not result:
        raise RuntimeError("Odoo authentication failed — check credentials")

    _uid_cache[cache_key] = result
    return result


def _execute_kw(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    """Call Odoo's object.execute_kw via JSON-RPC."""
    creds = _get_creds()
    uid = _authenticate()
    password = creds["api_key"] or creds["password"]
    return _jsonrpc(
        f"{creds['url']}/jsonrpc",
        "call",
        {
            "service": "object",
            "method": "execute_kw",
            "args": [
                creds["db"],
                uid,
                password,
                model,
                method,
                args,
                kwargs or {},
            ],
        },
    )


# ---------------------------------------------------------------------------
# MCP Tools — Configuration
# ---------------------------------------------------------------------------

@mcp.tool()
def odoo_configure(url: str, database: str, username: str, password: str) -> str:
    """Configure your Odoo CRM connection. Enter your Odoo URL, database name, login email, and password. Credentials are validated and saved on the server — you only need to do this once."""
    global _active_user

    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    # Validate credentials by attempting to authenticate
    try:
        result = _jsonrpc(
            f"{url}/jsonrpc",
            "call",
            {
                "service": "common",
                "method": "authenticate",
                "args": [database, username, password, {}],
            },
        )
        if not result:
            return json.dumps({
                "status": "error",
                "message": "Authentication failed. Please check your username and password."
            }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Could not connect to {url}. Error: {str(e)}"
        }, indent=2)

    # Store credentials
    creds = {
        "url": url,
        "db": database,
        "username": username,
        "password": password,
        "api_key": "",
    }
    _cred_store[username] = creds
    _active_user["email"] = username
    _save_creds_to_disk()

    # Also update uid cache
    cache_key = f"{url}|{username}"
    _uid_cache[cache_key] = result

    # Get server version for confirmation
    try:
        version = _jsonrpc(
            f"{url}/jsonrpc",
            "call",
            {"service": "common", "method": "version", "args": []},
        )
        ver = version.get("server_version", "unknown")
    except Exception:
        ver = "unknown"

    return json.dumps({
        "status": "connected",
        "uid": result,
        "server_version": ver,
        "url": url,
        "database": database,
        "username": username,
        "message": "Odoo CRM connected successfully! Your credentials are saved on the server — you won't need to enter them again."
    }, indent=2)


# ---------------------------------------------------------------------------
# MCP Tools — CRM Operations
# ---------------------------------------------------------------------------

@mcp.tool()
def odoo_test_connection() -> str:
    """Test the connection to your Odoo CRM instance and return server info."""
    creds = _get_creds()
    uid = _authenticate()
    version = _jsonrpc(
        f"{creds['url']}/jsonrpc",
        "call",
        {"service": "common", "method": "version", "args": []},
    )
    return json.dumps({
        "status": "connected",
        "uid": uid,
        "server_version": version.get("server_version", "unknown"),
        "url": creds["url"],
        "database": creds["db"],
    }, indent=2)


@mcp.tool()
def odoo_search_leads(
    stage: str = "",
    salesperson: str = "",
    company: str = "",
    email: str = "",
    min_revenue: float = 0,
    type: str = "",
    priority: int = -1,
    tag: str = "",
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Search CRM leads and opportunities. Filter by stage, salesperson, company, email, revenue, type (lead/opportunity), priority, or tag."""
    domain = []
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    if salesperson:
        domain.append(("user_id.name", "ilike", salesperson))
    if company:
        domain.append(("partner_name", "ilike", company))
    if email:
        domain.append(("email_from", "ilike", email))
    if min_revenue:
        domain.append(("expected_revenue", ">=", min_revenue))
    if type:
        domain.append(("type", "=", type))
    if priority >= 0:
        domain.append(("priority", "=", str(priority)))
    if tag:
        domain.append(("tag_ids.name", "ilike", tag))

    limit = min(limit, 100)

    fields = [
        "name", "partner_name", "contact_name", "email_from", "phone",
        "stage_id", "user_id", "expected_revenue", "probability",
        "priority", "type", "city", "country_id", "tag_ids",
        "create_date", "date_deadline", "activity_summary", "description",
    ]

    records = _execute_kw(
        "crm.lead", "search_read",
        [domain],
        {"fields": fields, "limit": limit, "offset": offset, "order": "create_date desc"},
    )
    total = _execute_kw("crm.lead", "search_count", [domain])
    return json.dumps({"leads": records, "total": total, "limit": limit, "offset": offset}, default=str, indent=2)


@mcp.tool()
def odoo_get_lead(lead_id: int) -> str:
    """Get full details for a specific CRM lead or opportunity by ID."""
    records = _execute_kw("crm.lead", "read", [[lead_id]], {"fields": []})
    if not records:
        return json.dumps({"error": f"Lead {lead_id} not found"})
    return json.dumps({"lead": records[0]}, default=str, indent=2)


@mcp.tool()
def odoo_create_lead(
    name: str,
    contact_name: str = "",
    partner_name: str = "",
    email_from: str = "",
    phone: str = "",
    expected_revenue: float = 0,
    description: str = "",
    priority: str = "0",
    type: str = "lead",
    stage: str = "",
    city: str = "",
    street: str = "",
    zip: str = "",
) -> str:
    """Create a new lead or opportunity in Odoo CRM."""
    vals = {"name": name, "type": type}
    if contact_name: vals["contact_name"] = contact_name
    if partner_name: vals["partner_name"] = partner_name
    if email_from: vals["email_from"] = email_from
    if phone: vals["phone"] = phone
    if expected_revenue: vals["expected_revenue"] = expected_revenue
    if description: vals["description"] = description
    if priority != "0": vals["priority"] = priority
    if city: vals["city"] = city
    if street: vals["street"] = street
    if zip: vals["zip"] = zip

    if stage:
        stages = _execute_kw(
            "crm.stage", "search_read",
            [[("name", "ilike", stage)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if stages:
            vals["stage_id"] = stages[0]["id"]

    lead_id = _execute_kw("crm.lead", "create", [vals])
    return json.dumps({"lead_id": lead_id, "status": "created"}, indent=2)


@mcp.tool()
def odoo_update_lead(
    lead_id: int,
    name: str = "",
    contact_name: str = "",
    partner_name: str = "",
    email_from: str = "",
    phone: str = "",
    expected_revenue: float = 0,
    description: str = "",
    priority: str = "",
    probability: float = -1,
    date_deadline: str = "",
    stage: str = "",
    type: str = "",
) -> str:
    """Update fields on an existing CRM lead or opportunity."""
    vals = {}
    if name: vals["name"] = name
    if contact_name: vals["contact_name"] = contact_name
    if partner_name: vals["partner_name"] = partner_name
    if email_from: vals["email_from"] = email_from
    if phone: vals["phone"] = phone
    if expected_revenue: vals["expected_revenue"] = expected_revenue
    if description: vals["description"] = description
    if priority: vals["priority"] = priority
    if probability >= 0: vals["probability"] = probability
    if date_deadline: vals["date_deadline"] = date_deadline
    if type: vals["type"] = type

    if stage:
        stages = _execute_kw(
            "crm.stage", "search_read",
            [[("name", "ilike", stage)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if stages:
            vals["stage_id"] = stages[0]["id"]

    if not vals:
        return json.dumps({"error": "No fields to update"})

    _execute_kw("crm.lead", "write", [[lead_id], vals])
    return json.dumps({"lead_id": lead_id, "status": "updated", "fields_updated": list(vals.keys())}, indent=2)


@mcp.tool()
def odoo_get_pipeline_stages() -> str:
    """Get all CRM pipeline stages with lead counts and total expected revenue per stage."""
    stages = _execute_kw(
        "crm.stage", "search_read",
        [[]],
        {"fields": ["name", "sequence", "is_won", "fold"], "order": "sequence asc"},
    )
    for s in stages:
        s["lead_count"] = _execute_kw("crm.lead", "search_count", [[("stage_id", "=", s["id"])]])
        leads = _execute_kw(
            "crm.lead", "search_read",
            [[("stage_id", "=", s["id"])]],
            {"fields": ["expected_revenue"], "limit": 0},
        )
        s["total_revenue"] = sum(l.get("expected_revenue", 0) or 0 for l in leads)
    return json.dumps({"stages": stages}, default=str, indent=2)


@mcp.tool()
def odoo_search_contacts(
    name: str = "",
    email: str = "",
    company: str = "",
    phone: str = "",
    limit: int = 20,
) -> str:
    """Search Odoo contacts/customers by name, email, company, or phone."""
    domain = [("customer_rank", ">", 0)]
    if name: domain.append(("name", "ilike", name))
    if email: domain.append(("email", "ilike", email))
    if company: domain.append(("parent_id.name", "ilike", company))
    if phone: domain.append(("phone", "ilike", phone))

    records = _execute_kw(
        "res.partner", "search_read",
        [domain],
        {
            "fields": ["name", "email", "phone", "mobile", "function", "parent_id", "city", "country_id", "website", "comment", "customer_rank"],
            "limit": min(limit, 100),
            "order": "name asc",
        },
    )
    return json.dumps({"contacts": records, "count": len(records)}, default=str, indent=2)


@mcp.tool()
def odoo_get_activities(
    lead_id: int = 0,
    user: str = "",
    activity_type: str = "",
    overdue_only: bool = False,
    limit: int = 50,
) -> str:
    """Get scheduled activities (calls, emails, meetings, to-dos) for CRM leads."""
    domain = [("res_model", "=", "crm.lead")]
    if lead_id: domain.append(("res_id", "=", lead_id))
    if user: domain.append(("user_id.name", "ilike", user))
    if activity_type: domain.append(("activity_type_id.name", "ilike", activity_type))
    if overdue_only:
        domain.append(("date_deadline", "<", date.today().isoformat()))

    records = _execute_kw(
        "mail.activity", "search_read",
        [domain],
        {
            "fields": ["res_id", "res_name", "activity_type_id", "summary", "note", "date_deadline", "user_id", "state"],
            "limit": min(limit, 100),
            "order": "date_deadline asc",
        },
    )
    return json.dumps({"activities": records, "count": len(records)}, default=str, indent=2)


@mcp.tool()
def odoo_create_activity(
    lead_id: int,
    date_deadline: str,
    activity_type: str = "To-Do",
    summary: str = "",
    note: str = "",
) -> str:
    """Schedule a new activity (call, email, meeting, to-do) on a CRM lead."""
    act_types = _execute_kw(
        "mail.activity.type", "search_read",
        [[("name", "ilike", activity_type)]],
        {"fields": ["id", "name"], "limit": 1},
    )
    act_type_id = act_types[0]["id"] if act_types else False

    model_ids = _execute_kw("ir.model", "search", [[("model", "=", "crm.lead")]])

    vals = {
        "res_model_id": model_ids[0],
        "res_id": lead_id,
        "activity_type_id": act_type_id,
        "summary": summary,
        "note": note,
        "date_deadline": date_deadline,
    }

    activity_id = _execute_kw("mail.activity", "create", [vals])
    return json.dumps({"activity_id": activity_id, "status": "created"}, indent=2)


@mcp.tool()
def odoo_log_note(lead_id: int, body: str) -> str:
    """Log an internal note on a CRM lead's chatter."""
    _execute_kw(
        "crm.lead", "message_post",
        [[lead_id]],
        {"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_note"},
    )
    return json.dumps({"lead_id": lead_id, "status": "note_logged"}, indent=2)


@mcp.tool()
def odoo_get_lead_messages(lead_id: int, limit: int = 20) -> str:
    """Get the message/chatter history for a CRM lead — includes emails, notes, and activity logs."""
    messages = _execute_kw(
        "mail.message", "search_read",
        [[("res_id", "=", lead_id), ("model", "=", "crm.lead")]],
        {
            "fields": ["date", "author_id", "body", "message_type", "subtype_id", "email_from"],
            "limit": min(limit, 50),
            "order": "date desc",
        },
    )
    return json.dumps({"messages": messages, "count": len(messages)}, default=str, indent=2)


@mcp.tool()
def odoo_convert_to_opportunity(lead_id: int) -> str:
    """Convert a CRM lead into an opportunity."""
    _execute_kw("crm.lead", "convert_opportunity", [[lead_id], False])
    return json.dumps({"lead_id": lead_id, "status": "converted_to_opportunity"}, indent=2)


# ---------------------------------------------------------------------------
# Raw ASGI middleware — backward compatible with header-based auth
# ---------------------------------------------------------------------------

class OdooCredentialsMiddleware:
    """Read X-ODOO-* headers and set them as env vars for the request.
    If no headers provided, stored credentials are used automatically."""

    HEADER_MAP = {
        b"x-odoo-url":      "ODOO_URL",
        b"x-odoo-db":       "ODOO_DB",
        b"x-odoo-username":  "ODOO_USERNAME",
        b"x-odoo-password":  "ODOO_PASSWORD",
        b"x-odoo-api-key":   "ODOO_API_KEY",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            for header_key, env_name in self.HEADER_MAP.items():
                value = headers.get(header_key, b"").decode("utf-8", errors="replace")
                if value:
                    os.environ[env_name] = value
                else:
                    # Clear env var so stored credentials are used instead
                    os.environ.pop(env_name, None)

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Build the ASGI app
# ---------------------------------------------------------------------------

sse_app = mcp.sse_app()
app = OdooCredentialsMiddleware(sse_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8766)

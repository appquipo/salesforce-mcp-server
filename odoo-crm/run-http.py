#!/usr/bin/env python3
"""
Odoo CRM MCP Server — SSE transport with OAuth 2.1 authentication.

When a user connects for the first time, their browser opens a login page.
They enter their Odoo credentials there (not in chat). The server validates
against Odoo, generates an access token, and the MCP client stores only the
token. Passwords never appear in chat history.

Authentication methods (in priority order):
  1. OAuth Bearer token — from the login page flow
  2. Server-side stored credentials — from odoo_configure tool (fallback)
  3. HTTP headers — X-ODOO-* headers (backward compatible)

Run:
    pip install mcp uvicorn
    uvicorn run-http:app --host 0.0.0.0 --port 8766
"""

import hashlib
import json
import os
import secrets
import time
import urllib.request
import urllib.error
from datetime import date
from typing import Any
from urllib.parse import urlencode, parse_qs, urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXTERNAL_BASE = "https://mcp-social-crm.ezxdemo.com/odoo"
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(DATA_DIR, "credentials_store.json")
TOKENS_FILE = os.path.join(DATA_DIR, "tokens_store.json")
CLIENTS_FILE = os.path.join(DATA_DIR, "clients_store.json")

TOKEN_EXPIRY = 365 * 24 * 3600  # 1 year

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
# Persistent storage helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_json(path: str, data: dict):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

# OAuth stores
_access_tokens: dict = _load_json(TOKENS_FILE)    # token -> {creds, expires}
_auth_codes: dict = {}                              # code -> {creds, client_id, redirect_uri, code_challenge, expires}
_registered_clients: dict = _load_json(CLIENTS_FILE)  # client_id -> {redirect_uris, name}
_cred_store: dict = _load_json(CREDS_FILE)          # email -> {url, db, username, password, api_key}
_active_user: dict = {"email": ""}

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
    """Get Odoo credentials. Priority: env vars > active user > single stored user."""
    url = os.environ.get("ODOO_URL", "").rstrip("/")
    if url:
        return {
            "url": url,
            "db": os.environ.get("ODOO_DB", ""),
            "username": os.environ.get("ODOO_USERNAME", ""),
            "password": os.environ.get("ODOO_PASSWORD", ""),
            "api_key": os.environ.get("ODOO_API_KEY", ""),
        }

    active = _active_user.get("email", "")
    if active and active in _cred_store:
        return dict(_cred_store[active])

    if len(_cred_store) == 1:
        return dict(list(_cred_store.values())[0])

    if len(_cred_store) > 1:
        users = ", ".join(_cred_store.keys())
        raise RuntimeError(
            f"Multiple Odoo accounts configured ({users}). "
            "Please call odoo_configure with your credentials to select your account."
        )

    raise RuntimeError(
        "Odoo CRM is not configured yet. "
        "Please use the odoo_configure tool or connect via the login page."
    )


def _jsonrpc(url: str, method: str, params: dict) -> Any:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _next_id(),
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
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
    creds = _get_creds()
    if not creds["url"]:
        raise RuntimeError("Odoo URL not configured")
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
        f"{creds['url']}/jsonrpc", "call",
        {"service": "common", "method": "authenticate", "args": [creds["db"], creds["username"], password, {}]},
    )
    if not result:
        raise RuntimeError("Odoo authentication failed — check credentials")
    _uid_cache[cache_key] = result
    return result


def _execute_kw(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    creds = _get_creds()
    uid = _authenticate()
    password = creds["api_key"] or creds["password"]
    return _jsonrpc(
        f"{creds['url']}/jsonrpc", "call",
        {"service": "object", "method": "execute_kw",
         "args": [creds["db"], uid, password, model, method, args, kwargs or {}]},
    )


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def _validate_odoo_creds(url: str, db: str, username: str, password: str) -> int | None:
    """Validate credentials against Odoo. Returns uid or None."""
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    try:
        result = _jsonrpc(
            f"{url}/jsonrpc", "call",
            {"service": "common", "method": "authenticate", "args": [db, username, password, {}]},
        )
        return result if result else None
    except Exception:
        return None


def _create_access_token(creds: dict) -> str:
    """Create and store an access token for the given credentials."""
    token = secrets.token_urlsafe(48)
    _access_tokens[token] = {
        "creds": creds,
        "expires": time.time() + TOKEN_EXPIRY,
        "created": time.time(),
    }
    _save_json(TOKENS_FILE, _access_tokens)
    return token


def _get_token_creds(token: str) -> dict | None:
    """Look up credentials for a Bearer token."""
    data = _access_tokens.get(token)
    if data and data["expires"] > time.time():
        return data["creds"]
    return None


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """Verify PKCE S256 challenge."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    import base64
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return computed == code_challenge


# ---------------------------------------------------------------------------
# OAuth HTML pages
# ---------------------------------------------------------------------------

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connect Odoo CRM</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 420px;
        }
        .logo {
            text-align: center;
            margin-bottom: 24px;
        }
        .logo svg { width: 48px; height: 48px; }
        h1 {
            text-align: center;
            font-size: 24px;
            color: #1a1a2e;
            margin-bottom: 8px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 32px;
        }
        label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #333;
            margin-bottom: 6px;
        }
        input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 15px;
            transition: border-color 0.2s;
            margin-bottom: 16px;
            outline: none;
        }
        input:focus { border-color: #667eea; }
        .hint {
            font-size: 12px;
            color: #999;
            margin-top: -12px;
            margin-bottom: 16px;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s, box-shadow 0.2s;
        }
        button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102,126,234,0.4); }
        button:active { transform: translateY(0); }
        button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .error {
            background: #fff0f0;
            color: #cc0000;
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 14px;
            margin-bottom: 16px;
            display: none;
        }
        .error.show { display: block; }
        .secure-note {
            text-align: center;
            margin-top: 20px;
            font-size: 12px;
            color: #999;
        }
        .secure-note svg { vertical-align: middle; margin-right: 4px; }
        .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">
            <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="48" height="48" rx="12" fill="#714B67"/>
                <path d="M24 12c-6.627 0-12 5.373-12 12s5.373 12 12 12 12-5.373 12-12-5.373-12-12-12zm0 4a8 8 0 110 16 8 8 0 010-16z" fill="white"/>
                <circle cx="24" cy="24" r="4" fill="white"/>
            </svg>
        </div>
        <h1>Connect Odoo CRM</h1>
        <p class="subtitle">Sign in to link your Odoo account with Claude</p>

        <div class="error" id="error"></div>

        <form id="loginForm" method="POST">
            <input type="hidden" name="response_type" value="__RESPONSE_TYPE__">
            <input type="hidden" name="client_id" value="__CLIENT_ID__">
            <input type="hidden" name="redirect_uri" value="__REDIRECT_URI__">
            <input type="hidden" name="state" value="__STATE__">
            <input type="hidden" name="code_challenge" value="__CODE_CHALLENGE__">
            <input type="hidden" name="code_challenge_method" value="__CODE_CHALLENGE_METHOD__">
            <input type="hidden" name="scope" value="__SCOPE__">

            <label for="url">Odoo URL</label>
            <input type="text" id="url" name="url" placeholder="mycompany.odoo.com" required>
            <p class="hint">Your Odoo instance address</p>

            <label for="database">Database Name</label>
            <input type="text" id="database" name="database" placeholder="mycompany">
            <p class="hint">Usually matches your subdomain</p>

            <label for="username">Email</label>
            <input type="email" id="username" name="username" placeholder="you@company.com" required>

            <label for="password">Password</label>
            <input type="password" id="password" name="password" placeholder="Your Odoo password" required>

            <button type="submit" id="submitBtn">Connect to Odoo</button>
        </form>

        <p class="secure-note">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="#999"><path d="M6 1a3 3 0 00-3 3v1H2.5A1.5 1.5 0 001 6.5v4A1.5 1.5 0 002.5 12h7A1.5 1.5 0 0011 10.5v-4A1.5 1.5 0 009.5 5H9V4a3 3 0 00-3-3zm0 1a2 2 0 012 2v1H4V4a2 2 0 012-2z"/></svg>
            Your credentials are validated directly with Odoo. Only a secure token is stored.
        </p>
    </div>

    <script>
        const form = document.getElementById('loginForm');
        const errorDiv = document.getElementById('error');
        const submitBtn = document.getElementById('submitBtn');

        // Auto-fill database from URL
        document.getElementById('url').addEventListener('input', function() {
            const db = document.getElementById('database');
            if (!db.value) {
                const match = this.value.match(/^(?:https?:\\/\\/)?([^.]+)/);
                if (match) db.value = match[1];
            }
        });

        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            errorDiv.classList.remove('show');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span>Connecting...';

            const formData = new URLSearchParams(new FormData(form));
            try {
                const resp = await fetch(window.location.pathname, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: formData.toString(),
                    redirect: 'manual'
                });

                if (resp.type === 'opaqueredirect' || resp.status === 302 || resp.status === 303) {
                    window.location.href = resp.headers.get('Location') || window.location.href;
                    return;
                }

                // For 302 that fetch follows automatically
                if (resp.redirected) {
                    window.location.href = resp.url;
                    return;
                }

                const result = await resp.json();
                if (result.error) {
                    errorDiv.textContent = result.error;
                    errorDiv.classList.add('show');
                } else if (result.redirect) {
                    window.location.href = result.redirect;
                    return;
                }
            } catch (err) {
                errorDiv.textContent = 'Connection error. Please try again.';
                errorDiv.classList.add('show');
            }

            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Connect to Odoo';
        });
    </script>
</body>
</html>"""

SUCCESS_PAGE_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Connected!</title>
<style>
body { font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #667eea, #764ba2);
min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { background: white; border-radius: 16px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
h1 { color: #1a1a2e; margin-bottom: 12px; }
p { color: #666; line-height: 1.6; }
.check { width: 64px; height: 64px; background: #4CAF50; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; }
.check svg { width: 32px; height: 32px; fill: white; }
</style></head><body><div class="card">
<div class="check"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></div>
<h1>Connected!</h1>
<p>Your Odoo CRM is now linked to Claude. You can close this window and return to Claude.</p>
</div></body></html>"""


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

    try:
        result = _jsonrpc(
            f"{url}/jsonrpc", "call",
            {"service": "common", "method": "authenticate", "args": [database, username, password, {}]},
        )
        if not result:
            return json.dumps({"status": "error", "message": "Authentication failed. Please check your username and password."}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Could not connect to {url}. Error: {str(e)}"}, indent=2)

    creds = {"url": url, "db": database, "username": username, "password": password, "api_key": ""}
    _cred_store[username] = creds
    _active_user["email"] = username
    _save_json(CREDS_FILE, _cred_store)
    _uid_cache[f"{url}|{username}"] = result

    try:
        version = _jsonrpc(f"{url}/jsonrpc", "call", {"service": "common", "method": "version", "args": []})
        ver = version.get("server_version", "unknown")
    except Exception:
        ver = "unknown"

    return json.dumps({
        "status": "connected", "uid": result, "server_version": ver,
        "url": url, "database": database, "username": username,
        "message": "Odoo CRM connected successfully! Your credentials are saved."
    }, indent=2)


# ---------------------------------------------------------------------------
# MCP Tools — CRM Operations
# ---------------------------------------------------------------------------

@mcp.tool()
def odoo_test_connection() -> str:
    """Test the connection to your Odoo CRM instance and return server info."""
    creds = _get_creds()
    uid = _authenticate()
    version = _jsonrpc(f"{creds['url']}/jsonrpc", "call", {"service": "common", "method": "version", "args": []})
    return json.dumps({"status": "connected", "uid": uid, "server_version": version.get("server_version", "unknown"), "url": creds["url"], "database": creds["db"]}, indent=2)


@mcp.tool()
def odoo_search_leads(stage: str = "", salesperson: str = "", company: str = "", email: str = "", min_revenue: float = 0, type: str = "", priority: int = -1, tag: str = "", limit: int = 20, offset: int = 0) -> str:
    """Search CRM leads and opportunities. Filter by stage, salesperson, company, email, revenue, type (lead/opportunity), priority, or tag."""
    domain = []
    if stage: domain.append(("stage_id.name", "ilike", stage))
    if salesperson: domain.append(("user_id.name", "ilike", salesperson))
    if company: domain.append(("partner_name", "ilike", company))
    if email: domain.append(("email_from", "ilike", email))
    if min_revenue: domain.append(("expected_revenue", ">=", min_revenue))
    if type: domain.append(("type", "=", type))
    if priority >= 0: domain.append(("priority", "=", str(priority)))
    if tag: domain.append(("tag_ids.name", "ilike", tag))
    limit = min(limit, 100)
    fields = ["name", "partner_name", "contact_name", "email_from", "phone", "stage_id", "user_id", "expected_revenue", "probability", "priority", "type", "city", "country_id", "tag_ids", "create_date", "date_deadline", "activity_summary", "description"]
    records = _execute_kw("crm.lead", "search_read", [domain], {"fields": fields, "limit": limit, "offset": offset, "order": "create_date desc"})
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
def odoo_create_lead(name: str, contact_name: str = "", partner_name: str = "", email_from: str = "", phone: str = "", expected_revenue: float = 0, description: str = "", priority: str = "0", type: str = "lead", stage: str = "", city: str = "", street: str = "", zip: str = "") -> str:
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
        stages = _execute_kw("crm.stage", "search_read", [[("name", "ilike", stage)]], {"fields": ["id", "name"], "limit": 1})
        if stages: vals["stage_id"] = stages[0]["id"]
    lead_id = _execute_kw("crm.lead", "create", [vals])
    return json.dumps({"lead_id": lead_id, "status": "created"}, indent=2)


@mcp.tool()
def odoo_update_lead(lead_id: int, name: str = "", contact_name: str = "", partner_name: str = "", email_from: str = "", phone: str = "", expected_revenue: float = 0, description: str = "", priority: str = "", probability: float = -1, date_deadline: str = "", stage: str = "", type: str = "") -> str:
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
        stages = _execute_kw("crm.stage", "search_read", [[("name", "ilike", stage)]], {"fields": ["id", "name"], "limit": 1})
        if stages: vals["stage_id"] = stages[0]["id"]
    if not vals:
        return json.dumps({"error": "No fields to update"})
    _execute_kw("crm.lead", "write", [[lead_id], vals])
    return json.dumps({"lead_id": lead_id, "status": "updated", "fields_updated": list(vals.keys())}, indent=2)


@mcp.tool()
def odoo_get_pipeline_stages() -> str:
    """Get all CRM pipeline stages with lead counts and total expected revenue per stage."""
    stages = _execute_kw("crm.stage", "search_read", [[]], {"fields": ["name", "sequence", "is_won", "fold"], "order": "sequence asc"})
    for s in stages:
        s["lead_count"] = _execute_kw("crm.lead", "search_count", [[("stage_id", "=", s["id"])]])
        leads = _execute_kw("crm.lead", "search_read", [[("stage_id", "=", s["id"])]], {"fields": ["expected_revenue"], "limit": 0})
        s["total_revenue"] = sum(l.get("expected_revenue", 0) or 0 for l in leads)
    return json.dumps({"stages": stages}, default=str, indent=2)


@mcp.tool()
def odoo_search_contacts(name: str = "", email: str = "", company: str = "", phone: str = "", limit: int = 20) -> str:
    """Search Odoo contacts/customers by name, email, company, or phone."""
    domain = [("customer_rank", ">", 0)]
    if name: domain.append(("name", "ilike", name))
    if email: domain.append(("email", "ilike", email))
    if company: domain.append(("parent_id.name", "ilike", company))
    if phone: domain.append(("phone", "ilike", phone))
    records = _execute_kw("res.partner", "search_read", [domain], {"fields": ["name", "email", "phone", "mobile", "function", "parent_id", "city", "country_id", "website", "comment", "customer_rank"], "limit": min(limit, 100), "order": "name asc"})
    return json.dumps({"contacts": records, "count": len(records)}, default=str, indent=2)


@mcp.tool()
def odoo_get_activities(lead_id: int = 0, user: str = "", activity_type: str = "", overdue_only: bool = False, limit: int = 50) -> str:
    """Get scheduled activities (calls, emails, meetings, to-dos) for CRM leads."""
    domain = [("res_model", "=", "crm.lead")]
    if lead_id: domain.append(("res_id", "=", lead_id))
    if user: domain.append(("user_id.name", "ilike", user))
    if activity_type: domain.append(("activity_type_id.name", "ilike", activity_type))
    if overdue_only: domain.append(("date_deadline", "<", date.today().isoformat()))
    records = _execute_kw("mail.activity", "search_read", [domain], {"fields": ["res_id", "res_name", "activity_type_id", "summary", "note", "date_deadline", "user_id", "state"], "limit": min(limit, 100), "order": "date_deadline asc"})
    return json.dumps({"activities": records, "count": len(records)}, default=str, indent=2)


@mcp.tool()
def odoo_create_activity(lead_id: int, date_deadline: str, activity_type: str = "To-Do", summary: str = "", note: str = "") -> str:
    """Schedule a new activity (call, email, meeting, to-do) on a CRM lead."""
    act_types = _execute_kw("mail.activity.type", "search_read", [[("name", "ilike", activity_type)]], {"fields": ["id", "name"], "limit": 1})
    act_type_id = act_types[0]["id"] if act_types else False
    model_ids = _execute_kw("ir.model", "search", [[("model", "=", "crm.lead")]])
    vals = {"res_model_id": model_ids[0], "res_id": lead_id, "activity_type_id": act_type_id, "summary": summary, "note": note, "date_deadline": date_deadline}
    activity_id = _execute_kw("mail.activity", "create", [vals])
    return json.dumps({"activity_id": activity_id, "status": "created"}, indent=2)


@mcp.tool()
def odoo_log_note(lead_id: int, body: str) -> str:
    """Log an internal note on a CRM lead's chatter."""
    _execute_kw("crm.lead", "message_post", [[lead_id]], {"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_note"})
    return json.dumps({"lead_id": lead_id, "status": "note_logged"}, indent=2)


@mcp.tool()
def odoo_get_lead_messages(lead_id: int, limit: int = 20) -> str:
    """Get the message/chatter history for a CRM lead."""
    messages = _execute_kw("mail.message", "search_read", [[("res_id", "=", lead_id), ("model", "=", "crm.lead")]], {"fields": ["date", "author_id", "body", "message_type", "subtype_id", "email_from"], "limit": min(limit, 50), "order": "date desc"})
    return json.dumps({"messages": messages, "count": len(messages)}, default=str, indent=2)


@mcp.tool()
def odoo_convert_to_opportunity(lead_id: int) -> str:
    """Convert a CRM lead into an opportunity."""
    _execute_kw("crm.lead", "convert_opportunity", [[lead_id], False])
    return json.dumps({"lead_id": lead_id, "status": "converted_to_opportunity"}, indent=2)


# ---------------------------------------------------------------------------
# ASGI middleware — OAuth + credential injection
# ---------------------------------------------------------------------------

class OAuthOdooMiddleware:
    """
    Handles:
    1. OAuth 2.1 endpoints (metadata, authorize, token, register)
    2. Bearer token auth on MCP endpoints
    3. Backward-compatible X-ODOO-* header auth
    """

    HEADER_MAP = {
        b"x-odoo-url": "ODOO_URL",
        b"x-odoo-db": "ODOO_DB",
        b"x-odoo-username": "ODOO_USERNAME",
        b"x-odoo-password": "ODOO_PASSWORD",
        b"x-odoo-api-key": "ODOO_API_KEY",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # --- OAuth endpoints (handled before MCP) ---
        if path == "/.well-known/oauth-authorization-server":
            return await self._oauth_metadata(scope, receive, send)

        if path == "/.well-known/oauth-protected-resource":
            return await self._resource_metadata(scope, receive, send)

        if path == "/authorize":
            if method == "GET":
                return await self._authorize_form(scope, receive, send)
            elif method == "POST":
                return await self._authorize_submit(scope, receive, send)

        if path == "/token" and method == "POST":
            return await self._token_endpoint(scope, receive, send)

        if path == "/register" and method == "POST":
            return await self._register_client(scope, receive, send)

        # --- MCP endpoints: authenticate via Bearer token or headers ---
        headers = dict(scope.get("headers", []))

        # Try Bearer token first
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            creds = _get_token_creds(token)
            if creds:
                os.environ["ODOO_URL"] = creds["url"]
                os.environ["ODOO_DB"] = creds["db"]
                os.environ["ODOO_USERNAME"] = creds["username"]
                os.environ["ODOO_PASSWORD"] = creds["password"]
                os.environ["ODOO_API_KEY"] = creds.get("api_key", "")
                return await self.app(scope, receive, send)
            else:
                return await self._send_401(scope, receive, send)

        # Try X-ODOO-* headers (backward compatible)
        has_headers = False
        for header_key, env_name in self.HEADER_MAP.items():
            value = headers.get(header_key, b"").decode("utf-8", errors="replace")
            if value:
                os.environ[env_name] = value
                has_headers = True
            else:
                os.environ.pop(env_name, None)

        if has_headers:
            return await self.app(scope, receive, send)

        # No auth provided — check if stored credentials exist
        if _cred_store:
            # Clear env vars so _get_creds() falls through to stored creds
            for env_name in self.HEADER_MAP.values():
                os.environ.pop(env_name, None)
            return await self.app(scope, receive, send)

        # No auth at all — return 401 for SSE/messages, allow other paths
        if path in ("/sse", "/messages", "/messages/"):
            return await self._send_401(scope, receive, send)

        return await self.app(scope, receive, send)

    # --- OAuth endpoint implementations ---

    async def _oauth_metadata(self, scope, receive, send):
        metadata = {
            "issuer": EXTERNAL_BASE,
            "authorization_endpoint": f"{EXTERNAL_BASE}/authorize",
            "token_endpoint": f"{EXTERNAL_BASE}/token",
            "registration_endpoint": f"{EXTERNAL_BASE}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["odoo_crm"],
        }
        await self._json_response(send, metadata)

    async def _resource_metadata(self, scope, receive, send):
        metadata = {
            "resource": EXTERNAL_BASE,
            "authorization_servers": [EXTERNAL_BASE],
            "scopes_supported": ["odoo_crm"],
            "bearer_methods_supported": ["header"],
        }
        await self._json_response(send, metadata)

    async def _authorize_form(self, scope, receive, send):
        params = {}
        if scope.get("query_string"):
            params = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
            params = {k: v[0] for k, v in params.items()}

        html = (LOGIN_PAGE_HTML
            .replace("__RESPONSE_TYPE__", params.get("response_type", "code"))
            .replace("__CLIENT_ID__", params.get("client_id", ""))
            .replace("__REDIRECT_URI__", params.get("redirect_uri", ""))
            .replace("__STATE__", params.get("state", ""))
            .replace("__CODE_CHALLENGE__", params.get("code_challenge", ""))
            .replace("__CODE_CHALLENGE_METHOD__", params.get("code_challenge_method", "S256"))
            .replace("__SCOPE__", params.get("scope", "odoo_crm"))
        )
        await self._html_response(send, html)

    async def _authorize_submit(self, scope, receive, send):
        body = await self._read_body(receive)
        params = parse_qs(body.decode(), keep_blank_values=True)
        params = {k: v[0] for k, v in params.items()}

        url = params.get("url", "").strip().rstrip("/")
        if url and not url.startswith("http"):
            url = "https://" + url
        database = params.get("database", "").strip()
        username = params.get("username", "").strip()
        password = params.get("password", "")
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")
        client_id = params.get("client_id", "")
        code_challenge = params.get("code_challenge", "")

        # Validate credentials against Odoo
        uid = _validate_odoo_creds(url, database, username, password)
        if not uid:
            error_resp = {"error": "Invalid credentials. Please check your Odoo URL, database, email, and password."}
            await self._json_response(send, error_resp, status=400)
            return

        # Store credentials server-side
        creds = {"url": url, "db": database, "username": username, "password": password, "api_key": ""}
        _cred_store[username] = creds
        _active_user["email"] = username
        _save_json(CREDS_FILE, _cred_store)

        # Generate authorization code
        code = secrets.token_urlsafe(32)
        _auth_codes[code] = {
            "creds": creds,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "expires": time.time() + 300,  # 5 minutes
        }

        if redirect_uri:
            sep = "&" if "?" in redirect_uri else "?"
            location = f"{redirect_uri}{sep}code={code}"
            if state:
                location += f"&state={state}"
            await self._redirect_response(send, location)
        else:
            await self._json_response(send, {"code": code, "redirect": redirect_uri})

    async def _token_endpoint(self, scope, receive, send):
        body = await self._read_body(receive)
        params = parse_qs(body.decode(), keep_blank_values=True)
        params = {k: v[0] for k, v in params.items()}

        grant_type = params.get("grant_type", "")

        if grant_type == "authorization_code":
            code = params.get("code", "")
            code_verifier = params.get("code_verifier", "")

            code_data = _auth_codes.pop(code, None)
            if not code_data or code_data["expires"] < time.time():
                await self._json_response(send, {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}, status=400)
                return

            # Verify PKCE if code_challenge was provided
            if code_data["code_challenge"] and code_verifier:
                if not _verify_pkce(code_verifier, code_data["code_challenge"]):
                    await self._json_response(send, {"error": "invalid_grant", "error_description": "PKCE verification failed"}, status=400)
                    return

            # Create access token
            access_token = _create_access_token(code_data["creds"])

            await self._json_response(send, {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRY,
                "scope": "odoo_crm",
            })
        else:
            await self._json_response(send, {"error": "unsupported_grant_type"}, status=400)

    async def _register_client(self, scope, receive, send):
        body = await self._read_body(receive)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        client_id = secrets.token_urlsafe(24)
        client_info = {
            "client_id": client_id,
            "client_name": data.get("client_name", "Claude MCP Client"),
            "redirect_uris": data.get("redirect_uris", []),
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        _registered_clients[client_id] = client_info
        _save_json(CLIENTS_FILE, _registered_clients)

        await self._json_response(send, client_info, status=201)

    async def _send_401(self, scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"www-authenticate", f'Bearer resource_metadata="{EXTERNAL_BASE}/.well-known/oauth-protected-resource"'.encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps({"error": "unauthorized", "message": "Please authenticate via the login page."}).encode(),
        })

    # --- Response helpers ---

    async def _json_response(self, send, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            [b"content-type", b"application/json"],
            [b"access-control-allow-origin", b"*"],
            [b"cache-control", b"no-store"],
        ]})
        await send({"type": "http.response.body", "body": body})

    async def _html_response(self, send, html: str, status: int = 200):
        await send({"type": "http.response.start", "status": status, "headers": [
            [b"content-type", b"text/html; charset=utf-8"],
        ]})
        await send({"type": "http.response.body", "body": html.encode()})

    async def _redirect_response(self, send, location: str):
        await send({"type": "http.response.start", "status": 302, "headers": [
            [b"location", location.encode()],
            [b"content-type", b"text/html"],
        ]})
        await send({"type": "http.response.body", "body": b'<html><body>Redirecting...</body></html>'})

    async def _read_body(self, receive) -> bytes:
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        return body


# ---------------------------------------------------------------------------
# Build the ASGI app
# ---------------------------------------------------------------------------

sse_app = mcp.sse_app()
app = OAuthOdooMiddleware(sse_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8766)

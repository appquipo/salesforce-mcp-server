#!/usr/bin/env python3
"""
Salesforce MCP Server (Stdio Transport)
Python port of mcp-server.php â runs locally, no server deployment needed.

Auth methods (configure via environment variables):
  1. Username + Password + Security Token (SOAP login)
  2. OAuth 2.0 Client Credentials flow (Connected App)

Usage: python3 mcp-server.py
"""

import os
import sys
import json
import hashlib
import re
import time
import tempfile
from typing import Optional, List, Dict, Any
from html import escape as html_escape
from urllib.parse import urlencode, quote

import httpx
from pydantic import BaseModel, Field, ConfigDict, field_validator
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# âââ Configuration (all from environment variables) ââââââââââââââââââââââââ
SF_USERNAME = os.environ.get("SF_USERNAME", "")
SF_PASSWORD = os.environ.get("SF_PASSWORD", "")
SF_SECURITY_TOKEN = os.environ.get("SF_SECURITY_TOKEN", "")
SF_CLIENT_ID = os.environ.get("SF_CLIENT_ID", "")
SF_CLIENT_SECRET = os.environ.get("SF_CLIENT_SECRET", "")
SF_LOGIN_URL = os.environ.get("SF_LOGIN_URL", "https://login.salesforce.com")
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "")
API_VERSION = os.environ.get("SF_API_VERSION", "v62.0")

_file_hash = hashlib.md5(os.path.abspath(__file__).encode()).hexdigest()
SESSION_CACHE = os.path.join(tempfile.gettempdir(), f"sf_mcp_session_{_file_hash}.json")

# âââ Initialize MCP Server âââââââââââââââââââââââââââââââââââââââââââââââââ
mcp = FastMCP("salesforce_mcp", transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


# âââ Auth Method Detection âââââââââââââââââââââââââââââââââââââââââââââââââ
def _get_auth_method() -> str:
    if SF_CLIENT_ID and SF_CLIENT_SECRET:
        return "oauth"
    if SF_USERNAME and SF_PASSWORD:
        return "password"
    return "none"


# âââ HTTP Helper âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def _sf_http(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None,
             body: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous HTTP request helper for Salesforce API calls."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.request(method, url, headers=headers, content=body)
        return {"status": response.status_code, "body": response.text}


def _xml_esc(s: str) -> str:
    return html_escape(s, quote=True)


# âââ Salesforce Auth âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def _sf_load_session() -> Optional[Dict[str, Any]]:
    if os.path.exists(SESSION_CACHE):
        try:
            with open(SESSION_CACHE, "r") as f:
                data = json.load(f)
            if data and data.get("expiry", 0) > time.time():
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _sf_save_session(access_token: str, instance_url: str) -> Dict[str, Any]:
    data = {
        "access_token": access_token,
        "instance_url": instance_url,
        "expiry": int(time.time()) + 5400,  # 90 minutes
    }
    try:
        with open(SESSION_CACHE, "w") as f:
            json.dump(data, f)
    except IOError:
        pass
    return data


def _sf_oauth_login() -> Dict[str, Any]:
    r = _sf_http(
        SF_LOGIN_URL + "/services/oauth2/token",
        "POST",
        {"Content-Type": "application/x-www-form-urlencoded"},
        urlencode({
            "grant_type": "client_credentials",
            "client_id": SF_CLIENT_ID,
            "client_secret": SF_CLIENT_SECRET,
        }),
    )
    d = json.loads(r["body"]) if r["body"] else {}
    if r["status"] != 200 or "access_token" not in d:
        err = d.get("error_description") or d.get("error") or f"HTTP {r['status']}"
        raise Exception(f"OAuth login failed: {err}")
    return _sf_save_session(d["access_token"], d.get("instance_url") or SF_INSTANCE_URL)


def _sf_soap_login() -> Dict[str, Any]:
    api_num = API_VERSION.lstrip("v")
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
        '<env:Body><n1:login xmlns:n1="urn:partner.soap.sforce.com">'
        f'<n1:username>{_xml_esc(SF_USERNAME)}</n1:username>'
        f'<n1:password>{_xml_esc(SF_PASSWORD + SF_SECURITY_TOKEN)}</n1:password>'
        '</n1:login></env:Body></env:Envelope>'
    )
    r = _sf_http(
        SF_LOGIN_URL + "/services/Soap/u/" + api_num,
        "POST",
        {"Content-Type": "text/xml", "SOAPAction": "login"},
        xml,
    )
    if r["status"] != 200:
        m = re.search(r"<faultstring>([^<]+)</faultstring>", r["body"])
        fault = m.group(1) if m else f"HTTP {r['status']}"
        raise Exception(f"SOAP login failed: {fault}")
    s = re.search(r"<sessionId>([^<]+)</sessionId>", r["body"])
    u = re.search(r"<serverUrl>([^<]+)</serverUrl>", r["body"])
    if not s or not u:
        raise Exception("Cannot parse SOAP login response")
    inst = re.search(r"(https://[^/]+)", u.group(1))
    return _sf_save_session(s.group(1), inst.group(1) if inst else "")


def _sf_login() -> Dict[str, Any]:
    method = _get_auth_method()
    if method == "oauth":
        return _sf_oauth_login()
    if method == "password":
        return _sf_soap_login()
    raise Exception(
        "No Salesforce credentials configured. Set SF_USERNAME/SF_PASSWORD/SF_SECURITY_TOKEN "
        "or SF_CLIENT_ID/SF_CLIENT_SECRET environment variables."
    )


def _sf_ensure_session() -> Dict[str, Any]:
    return _sf_load_session() or _sf_login()


# âââ REST API ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def _sf_api(method: str, path: str, body: Any = None) -> Any:
    session = _sf_ensure_session()
    url = session["instance_url"] + "/services/data/" + API_VERSION + path
    headers = {
        "Authorization": "Bearer " + session["access_token"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    r = _sf_http(url, method, headers, json.dumps(body) if body is not None else None)

    # Re-auth on 401
    if r["status"] == 401:
        try:
            os.unlink(SESSION_CACHE)
        except OSError:
            pass
        session = _sf_login()
        headers["Authorization"] = "Bearer " + session["access_token"]
        r = _sf_http(url, method, headers, json.dumps(body) if body is not None else None)

    d = None
    if r["body"].strip():
        try:
            d = json.loads(r["body"])
        except json.JSONDecodeError:
            d = r["body"]

    if r["status"] >= 400:
        if isinstance(d, list) and d and "message" in d[0]:
            msg = "; ".join(item.get("message", "") for item in d)
        elif isinstance(d, dict) and "message" in d:
            msg = d["message"]
        else:
            msg = d if isinstance(d, str) else json.dumps(d)
        raise Exception(f"Salesforce API error ({r['status']}): {msg}")

    return d


def _sf_soql(q: str) -> Any:
    return _sf_api("GET", "/query/?q=" + quote(q, safe=""))


def _sf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t").replace("\0", "")


# âââ Pydantic Input Models âââââââââââââââââââââââââââââââââââââââââââââââââ

class SearchInput(BaseModel):
    """Input for search tools with query and optional limit."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Search term (name, email, company, or phone)", min_length=1, max_length=500)
    limit: Optional[int] = Field(default=10, description="Max results to return, 1-50 (default 10)", ge=1, le=50)


class LeadIdInput(BaseModel):
    """Input for tools that need a single lead ID."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    lead_id: str = Field(..., description="Salesforce Lead ID (e.g., 00Qxx...)", min_length=1)


class CreateLeadInput(BaseModel):
    """Input for creating a new lead."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    fields: Dict[str, Any] = Field(..., description="Lead fields to set. Must include LastName and Company.")


class UpdateLeadInput(BaseModel):
    """Input for updating an existing lead."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    lead_id: str = Field(..., description="Salesforce Lead ID", min_length=1)
    fields: Dict[str, Any] = Field(..., description="Fields to update (key-value pairs)")


class ChangeOwnerInput(BaseModel):
    """Input for changing lead owner."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    lead_id: str = Field(..., description="Salesforce Lead ID", min_length=1)
    new_owner_id: str = Field(..., description="User ID of new owner (use sf_search_users to find)", min_length=1)


class LogActivityInput(BaseModel):
    """Input for logging an activity on a lead."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    lead_id: str = Field(..., description="Lead ID to associate the activity with", min_length=1)
    subject: str = Field(..., description="Activity subject line", min_length=1)
    description: Optional[str] = Field(default="", description="Activity details/notes")
    status: Optional[str] = Field(default="Completed", description="Status: Completed, Not Started, etc.")
    priority: Optional[str] = Field(default="Normal", description="Priority: High, Normal, Low")
    activity_date: Optional[str] = Field(default=None, description="Date YYYY-MM-DD (default: today)")


class SearchUsersInput(BaseModel):
    """Input for searching Salesforce users."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(..., description="Name to search for", min_length=1)


class DescribeObjectInput(BaseModel):
    """Input for describing a Salesforce object."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    object: str = Field(default="Lead", description="Object API name (e.g., Lead, Contact, Account)")

    @field_validator("object")
    @classmethod
    def sanitize_object_name(cls, v: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "", v)


class SoqlQueryInput(BaseModel):
    """Input for running a SOQL query."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="SOQL SELECT query string", min_length=1)


# âââ Tool Implementations ââââââââââââââââââââââââââââââââââââââââââââââââââ

@mcp.tool(
    name="sf_search_leads",
    annotations={
        "title": "Search Salesforce Leads",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_search_leads(params: SearchInput) -> str:
    """Search for leads by name, email, company, or phone.

    Returns matching leads with key fields like name, company, email, status, owner, etc.
    """
    q = _sf_escape(params.query)
    lim = min(params.limit or 10, 50)
    r = _sf_soql(
        "SELECT Id,FirstName,LastName,Company,Title,Email,Phone,Rating,Status,"
        "LeadSource,Website,Country,City,NumberOfEmployees,OwnerId,Owner.Name,"
        "CreatedDate,LastModifiedDate "
        "FROM Lead WHERE Name LIKE '%" + q + "%' OR Email LIKE '%" + q + "%' "
        "OR Company LIKE '%" + q + "%' OR Phone LIKE '%" + q + "%' "
        "ORDER BY LastModifiedDate DESC LIMIT " + str(lim)
    )
    records = []
    for x in r.get("records", []):
        records.append({
            "id": x.get("Id"),
            "name": ((x.get("FirstName") or "") + " " + (x.get("LastName") or "")).strip(),
            "company": x.get("Company"),
            "title": x.get("Title"),
            "email": x.get("Email"),
            "phone": x.get("Phone"),
            "rating": x.get("Rating"),
            "status": x.get("Status"),
            "source": x.get("LeadSource"),
            "website": x.get("Website"),
            "country": x.get("Country"),
            "owner": (x.get("Owner") or {}).get("Name"),
            "ownerId": x.get("OwnerId"),
        })
    return json.dumps({"total": r.get("totalSize", 0), "records": records}, indent=2)


@mcp.tool(
    name="sf_get_lead",
    annotations={
        "title": "Get Lead Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_get_lead(params: LeadIdInput) -> str:
    """Get full details of a single lead by its Salesforce ID."""
    result = _sf_api("GET", "/sobjects/Lead/" + params.lead_id)
    return json.dumps(result, indent=2)


@mcp.tool(
    name="sf_create_lead",
    annotations={
        "title": "Create Salesforce Lead",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
def sf_create_lead(params: CreateLeadInput) -> str:
    """Create a new lead. Pass any valid Lead fields inside the 'fields' object. LastName and Company are required."""
    fields = params.fields
    if "LastName" not in fields or "Company" not in fields:
        return json.dumps({"error": "LastName and Company are required to create a lead."})
    r = _sf_api("POST", "/sobjects/Lead", fields)
    return json.dumps({"success": True, "id": r.get("id") if isinstance(r, dict) else None}, indent=2)


@mcp.tool(
    name="sf_update_lead",
    annotations={
        "title": "Update Salesforce Lead",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_update_lead(params: UpdateLeadInput) -> str:
    """Update fields on an existing lead. Pass only the fields you want to change."""
    if not params.fields:
        return json.dumps({"error": "No fields provided to update."})
    _sf_api("PATCH", "/sobjects/Lead/" + params.lead_id, params.fields)
    return json.dumps({"success": True}, indent=2)


@mcp.tool(
    name="sf_delete_lead",
    annotations={
        "title": "Delete Salesforce Lead",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
def sf_delete_lead(params: LeadIdInput) -> str:
    """Delete a lead by ID. This action is permanent."""
    _sf_api("DELETE", "/sobjects/Lead/" + params.lead_id)
    return json.dumps({"success": True}, indent=2)


@mcp.tool(
    name="sf_change_owner",
    annotations={
        "title": "Change Lead Owner",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_change_owner(params: ChangeOwnerInput) -> str:
    """Change the owner of a lead to a different Salesforce user."""
    _sf_api("PATCH", "/sobjects/Lead/" + params.lead_id, {"OwnerId": params.new_owner_id})
    return json.dumps({"success": True}, indent=2)


@mcp.tool(
    name="sf_log_activity",
    annotations={
        "title": "Log Activity on Lead",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
def sf_log_activity(params: LogActivityInput) -> str:
    """Log a task/activity on a lead (e.g., call, email, meeting note)."""
    from datetime import date as date_cls
    task = {
        "WhoId": params.lead_id,
        "Subject": params.subject,
        "Description": params.description or "",
        "Status": params.status or "Completed",
        "Priority": params.priority or "Normal",
        "TaskSubtype": "Task",
        "ActivityDate": params.activity_date or date_cls.today().isoformat(),
    }
    r = _sf_api("POST", "/sobjects/Task", task)
    return json.dumps({"success": True, "id": r.get("id") if isinstance(r, dict) else None}, indent=2)


@mcp.tool(
    name="sf_search_users",
    annotations={
        "title": "Search Salesforce Users",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_search_users(params: SearchUsersInput) -> str:
    """Search active Salesforce users by name. Useful for finding user IDs for owner assignment."""
    q = _sf_escape(params.name)
    r = _sf_soql(
        "SELECT Id,Name,Email,IsActive,Profile.Name FROM User "
        "WHERE Name LIKE '%" + q + "%' AND IsActive=true ORDER BY Name LIMIT 20"
    )
    users = []
    for u in r.get("records", []):
        users.append({
            "id": u.get("Id"),
            "name": u.get("Name"),
            "email": u.get("Email"),
            "profile": (u.get("Profile") or {}).get("Name"),
        })
    return json.dumps({"total": r.get("totalSize", 0), "users": users}, indent=2)


@mcp.tool(
    name="sf_describe_object",
    annotations={
        "title": "Describe Salesforce Object",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_describe_object(params: DescribeObjectInput) -> str:
    """List all fields on a Salesforce object (Lead, Contact, Account, etc.)."""
    obj = params.object or "Lead"
    r = _sf_api("GET", "/sobjects/" + obj + "/describe")
    fields = []
    for f in r.get("fields", []):
        pv = f.get("picklistValues", [])
        fields.append({
            "name": f.get("name"),
            "label": f.get("label"),
            "type": f.get("type"),
            "custom": f.get("custom", False),
            "updateable": f.get("updateable", False),
            "required": not f.get("nillable", True) and not f.get("defaultedOnCreate", False),
            "length": f.get("length"),
            "picklistValues": [p["value"] for p in pv if p.get("active")] if pv else None,
        })
    return json.dumps({"object": obj, "total": len(fields), "fields": fields}, indent=2)


@mcp.tool(
    name="sf_soql_query",
    annotations={
        "title": "Run SOQL Query",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_soql_query(params: SoqlQueryInput) -> str:
    """Run a read-only SOQL query against Salesforce. Only SELECT queries are allowed."""
    query = params.query
    if re.match(r"^\s*(INSERT|UPDATE|DELETE|UPSERT|MERGE)", query, re.IGNORECASE):
        return json.dumps({"error": "Only SELECT queries are allowed via sf_soql_query."})
    r = _sf_soql(query)
    return json.dumps({
        "totalSize": r.get("totalSize", 0),
        "done": r.get("done", True),
        "records": r.get("records", []),
    }, indent=2)


@mcp.tool(
    name="sf_search_contacts",
    annotations={
        "title": "Search Salesforce Contacts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_search_contacts(params: SearchInput) -> str:
    """Search for contacts by name or email."""
    q = _sf_escape(params.query)
    lim = min(params.limit or 10, 50)
    r = _sf_soql(
        "SELECT Id,FirstName,LastName,Email,Phone,Account.Name,Title,OwnerId,Owner.Name "
        "FROM Contact WHERE Name LIKE '%" + q + "%' OR Email LIKE '%" + q + "%' "
        "ORDER BY LastModifiedDate DESC LIMIT " + str(lim)
    )
    records = []
    for x in r.get("records", []):
        records.append({
            "id": x.get("Id"),
            "name": ((x.get("FirstName") or "") + " " + (x.get("LastName") or "")).strip(),
            "email": x.get("Email"),
            "phone": x.get("Phone"),
            "account": (x.get("Account") or {}).get("Name"),
            "title": x.get("Title"),
            "owner": (x.get("Owner") or {}).get("Name"),
        })
    return json.dumps({"total": r.get("totalSize", 0), "records": records}, indent=2)


@mcp.tool(
    name="sf_search_accounts",
    annotations={
        "title": "Search Salesforce Accounts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_search_accounts(params: SearchInput) -> str:
    """Search for accounts by name."""
    q = _sf_escape(params.query)
    lim = min(params.limit or 10, 50)
    r = _sf_soql(
        "SELECT Id,Name,Industry,Website,Phone,BillingCity,BillingCountry,"
        "NumberOfEmployees,OwnerId,Owner.Name "
        "FROM Account WHERE Name LIKE '%" + q + "%' "
        "ORDER BY LastModifiedDate DESC LIMIT " + str(lim)
    )
    records = []
    for x in r.get("records", []):
        records.append({
            "id": x.get("Id"),
            "name": x.get("Name"),
            "industry": x.get("Industry"),
            "website": x.get("Website"),
            "phone": x.get("Phone"),
            "city": x.get("BillingCity"),
            "country": x.get("BillingCountry"),
            "employees": x.get("NumberOfEmployees"),
            "owner": (x.get("Owner") or {}).get("Name"),
        })
    return json.dumps({"total": r.get("totalSize", 0), "records": records}, indent=2)


@mcp.tool(
    name="sf_search_opportunities",
    annotations={
        "title": "Search Salesforce Opportunities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def sf_search_opportunities(params: SearchInput) -> str:
    """Search for opportunities by name or account name."""
    q = _sf_escape(params.query)
    lim = min(params.limit or 10, 50)
    r = _sf_soql(
        "SELECT Id,Name,StageName,Amount,CloseDate,Account.Name,OwnerId,Owner.Name,"
        "Probability,IsClosed,IsWon "
        "FROM Opportunity WHERE Name LIKE '%" + q + "%' OR Account.Name LIKE '%" + q + "%' "
        "ORDER BY LastModifiedDate DESC LIMIT " + str(lim)
    )
    records = []
    for x in r.get("records", []):
        records.append({
            "id": x.get("Id"),
            "name": x.get("Name"),
            "stage": x.get("StageName"),
            "amount": x.get("Amount"),
            "closeDate": x.get("CloseDate"),
            "account": (x.get("Account") or {}).get("Name"),
            "probability": x.get("Probability"),
            "isClosed": x.get("IsClosed", False),
            "isWon": x.get("IsWon", False),
            "owner": (x.get("Owner") or {}).get("Name"),
        })
    return json.dumps({"total": r.get("totalSize", 0), "records": records}, indent=2)


# âââ Entry Point âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
if __name__ == "__main__":
    print(f"[salesforce-mcp] Auth method: {_get_auth_method()}", file=sys.stderr)
    mcp.run()

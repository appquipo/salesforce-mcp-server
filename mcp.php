<?php
/**
 * Salesforce MCP Server (Streamable HTTP Transport)
 * Public Edition — supports any Salesforce org.
 *
 * Auth methods (configure via environment variables):
 *   1. Username + Password + Security Token (SOAP login)
 *   2. OAuth 2.0 Client Credentials flow (Connected App)
 *
 * Deploy: drop this file on any PHP 8.0+ web server.
 * Docs:   See README.md for full setup instructions.
 */

// ─── CORS ──────────────────────────────────────────────────────────────────────────
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Mcp-Session-Id');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

// ─── Configuration (all from environment variables) ────────────────────
// Auth method 1: Username + Password + Security Token
define('SF_USERNAME',       getenv('SF_USERNAME')       ?: '');
define('SF_PASSWORD',       getenv('SF_PASSWORD')       ?: '');
define('SF_SECURITY_TOKEN', getenv('SF_SECURITY_TOKEN') ?: '');

// Auth method 2: OAuth 2.0 Client Credentials
define('SF_CLIENT_ID',      getenv('SF_CLIENT_ID')      ?: '');
define('SF_CLIENT_SECRET',  getenv('SF_CLIENT_SECRET')  ?: '');

// Shared config
define('SF_LOGIN_URL',  getenv('SF_LOGIN_URL')  ?: 'https://login.salesforce.com');
define('SF_INSTANCE_URL', getenv('SF_INSTANCE_URL') ?: ''); // Required for OAuth
define('API_VERSION',   getenv('SF_API_VERSION') ?: 'v62.0');

// Session cache
define('SESSION_CACHE', sys_get_temp_dir() . '/sf_mcp_session_' . md5(__FILE__) . '.json');

// ─── Auth Method Detection ───────────────────────────────────────────────────
function get_auth_method(): string {
    if (SF_CLIENT_ID && SF_CLIENT_SECRET) return 'oauth';
    if (SF_USERNAME && SF_PASSWORD)       return 'password';
    return 'none';
}

// ─── HTTP Helper ───────────────────────────────────────────────────────────
function sf_http(string $url, string $method = 'GET', array $headers = [], ?string $body = null): array {
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_CUSTOMREQUEST  => $method,
        CURLOPT_FOLLOWLOCATION => true,
    ]);
    $headerLines = [];
    foreach ($headers as $k => $v) $headerLines[] = "$k: $v";
    if ($headerLines) curl_setopt($ch, CURLOPT_HTTPHEADER, $headerLines);
    if ($body !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, $body);

    $response   = curl_exec($ch);
    $statusCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error      = curl_error($ch);
    curl_close($ch);

    if ($response === false) throw new Exception("HTTP request failed: $error");
    return ['status' => $statusCode, 'body' => $response];
}

function xml_esc(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES | ENT_XML1, 'UTF-8');
}

// ─── Salesforce Auth ───────────────────────────────────────────────────
function sf_load_session(): ?array {
    if (file_exists(SESSION_CACHE)) {
        $data = json_decode(file_get_contents(SESSION_CACHE), true);
        if ($data && isset($data['expiry']) && $data['expiry'] > time()) return $data;
    }
    return null;
}

function sf_save_session(string $accessToken, string $instanceUrl): array {
    $data = [
        'access_token' => $accessToken,
        'instance_url' => $instanceUrl,
        'expiry'       => time() + 5400, // 90 minutes
    ];
    file_put_contents(SESSION_CACHE, json_encode($data));
    return $data;
}

function sf_oauth_login(): array {
    $r = sf_http(SF_LOGIN_URL . '/services/oauth2/token', 'POST', [
        'Content-Type' => 'application/x-www-form-urlencoded',
    ], http_build_query([
        'grant_type'    => 'client_credentials',
        'client_id'     => SF_CLIENT_ID,
        'client_secret' => SF_CLIENT_SECRET,
    ]));

    $d = json_decode($r['body'], true);
    if ($r['status'] !== 200 || !isset($d['access_token'])) {
        throw new Exception('OAuth login failed: ' . ($d['error_description'] ?? $d['error'] ?? "HTTP {$r['status']}"));
    }
    return sf_save_session($d['access_token'], $d['instance_url'] ?? SF_INSTANCE_URL);
}

function sf_soap_login(): array {
    $xml = '<?xml version="1.0" encoding="utf-8"?>'
        . '<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        . 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        . 'xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
        . '<env:Body><n1:login xmlns:n1="urn:partner.soap.sforce.com">'
        . '<n1:username>' . xml_esc(SF_USERNAME) . '</n1:username>'
        . '<n1:password>' . xml_esc(SF_PASSWORD . SF_SECURITY_TOKEN) . '</n1:password>'
        . '</n1:login></env:Body></env:Envelope>';

    $r = sf_http(
        SF_LOGIN_URL . '/services/Soap/u/' . ltrim(API_VERSION, 'v'),
        'POST',
        ['Content-Type' => 'text/xml', 'SOAPAction' => 'login'],
        $xml
    );

    if ($r['status'] !== 200) {
        preg_match('/<faultstring>([^<]+)<\/faultstring>/', $r['body'], $m);
        throw new Exception('SOAP login failed: ' . ($m[1] ?? "HTTP {$r['status']}"));
    }

    preg_match('/<sessionId>([^<]+)<\/sessionId>/', $r['body'], $s);
    preg_match('/<serverUrl>([^<]+)<\/serverUrl>/', $r['body'], $u);
    if (!$s || !$u) throw new Exception('Cannot parse SOAP login response');

    preg_match('/(https:\/\/[^\/]+)/', $u[1], $inst);
    return sf_save_session($s[1], $inst[1]);
}

function sf_login(): array {
    $method = get_auth_method();
    if ($method === 'oauth')    return sf_oauth_login();
    if ($method === 'password') return sf_soap_login();
    throw new Exception('No Salesforce credentials configured. Set SF_USERNAME/SF_PASSWORD/SF_SECURITY_TOKEN or SF_CLIENT_ID/SF_CLIENT_SECRET environment variables.');
}

function sf_ensure_session(): array {
    return sf_load_session() ?? sf_login();
}

// ─── REST API ──────────────────────────────────────────────────────────
function sf_api(string $method, string $path, $body = null) {
    $session = sf_ensure_session();
    $url = $session['instance_url'] . '/services/data/' . API_VERSION . $path;
    $headers = [
        'Authorization' => 'Bearer ' . $session['access_token'],
        'Content-Type'  => 'application/json',
        'Accept'        => 'application/json',
    ];

    $r = sf_http($url, $method, $headers, $body !== null ? json_encode($body) : null);

    // Retry on 401 (expired token)
    if ($r['status'] === 401) {
        @unlink(SESSION_CACHE);
        $session = sf_login();
        $headers['Authorization'] = 'Bearer ' . $session['access_token'];
        $r = sf_http($url, $method, $headers, $body !== null ? json_encode($body) : null);
    }

    $d = null;
    if (trim($r['body'])) {
        $d = json_decode($r['body'], true);
        if ($d === null) $d = $r['body'];
    }

    if ($r['status'] >= 400) {
        if (is_array($d) && isset($d[0]['message'])) {
            $msg = implode('; ', array_column($d, 'message'));
        } elseif (is_array($d) && isset($d['message'])) {
            $msg = $d['message'];
        } else {
            $msg = is_string($d) ? $d : json_encode($d);
        }
        throw new Exception("Salesforce API error ({$r['status']}): $msg");
    }

    return $d;
}

function sf_soql(string $q) {
    return sf_api('GET', '/query/?q=' . urlencode($q));
}

// ─── SOQL Sanitization ────────────────────────────────────────────────
function sf_escape(string $s): string {
    return str_replace(
        ["\\\\", "'",  "\n", "\r", "\t", "\0"],
        ["\\\\\\\\", "\\'", "\\n", "\\r", "\\t", ""],
        $s
    );
}

// ─── Tool Implementations ──────────────────────────────────────────────

function sf_search_leads(array $args): array {
    $q   = sf_escape($args['query']);
    $lim = min((int)($args['limit'] ?? 10), 50);
    $r = sf_soql(
        "SELECT Id,FirstName,LastName,Company,Title,Email,Phone,Rating,Status,"
        . "LeadSource,Website,Country,City,NumberOfEmployees,OwnerId,Owner.Name,"
        . "CreatedDate,LastModifiedDate "
        . "FROM Lead WHERE Name LIKE '%{$q}%' OR Email LIKE '%{$q}%' "
        . "OR Company LIKE '%{$q}%' OR Phone LIKE '%{$q}%' "
        . "ORDER BY LastModifiedDate DESC LIMIT {$lim}"
    );
    $records = [];
    foreach (($r['records'] ?? []) as $x) {
        $records[] = [
            'id'        => $x['Id'] ?? null,
            'name'      => trim(($x['FirstName'] ?? '') . ' ' . ($x['LastName'] ?? '')),
            'company'   => $x['Company'] ?? null,
            'title'     => $x['Title'] ?? null,
            'email'     => $x['Email'] ?? null,
            'phone'     => $x['Phone'] ?? null,
            'rating'    => $x['Rating'] ?? null,
            'status'    => $x['Status'] ?? null,
            'source'    => $x['LeadSource'] ?? null,
            'website'   => $x['Website'] ?? null,
            'country'   => $x['Country'] ?? null,
            'owner'     => $x['Owner']['Name'] ?? null,
            'ownerId'   => $x['OwnerId'] ?? null,
        ];
    }
    return ['total' => $r['totalSize'] ?? 0, 'records' => $records];
}

function sf_get_lead(array $args): array {
    return sf_api('GET', '/sobjects/Lead/' . $args['lead_id']);
}

function sf_create_lead(array $args): array {
    $fields = $args['fields'] ?? [];
    if (!isset($fields['LastName']) || !isset($fields['Company'])) {
        throw new Exception('LastName and Company are required to create a lead.');
    }
    $r = sf_api('POST', '/sobjects/Lead', $fields);
    return ['success' => true, 'id' => $r['id'] ?? null];
}

function sf_update_lead(array $args): array {
    $fields = $args['fields'] ?? [];
    if (empty($fields)) throw new Exception('No fields provided to update.');
    sf_api('PATCH', '/sobjects/Lead/' . $args['lead_id'], $fields);
    return ['success' => true];
}

function sf_delete_lead(array $args): array {
    sf_api('DELETE', '/sobjects/Lead/' . $args['lead_id']);
    return ['success' => true];
}

function sf_change_owner(array $args): array {
    sf_api('PATCH', '/sobjects/Lead/' . $args['lead_id'], ['OwnerId' => $args['new_owner_id']]);
    return ['success' => true];
}

function sf_log_activity(array $args): array {
    $task = [
        'WhoId'       => $args['lead_id'],
        'Subject'     => $args['subject'],
        'Description' => $args['description'] ?? '',
        'Status'      => $args['status'] ?? 'Completed',
        'Priority'    => $args['priority'] ?? 'Normal',
        'TaskSubtype' => 'Task',
        'ActivityDate' => $args['activity_date'] ?? date('Y-m-d'),
    ];
    $r = sf_api('POST', '/sobjects/Task', $task);
    return ['success' => true, 'id' => $r['id'] ?? null];
}

function sf_search_users(array $args): array {
    $q = sf_escape($args['name']);
    $r = sf_soql(
        "SELECT Id,Name,Email,IsActive,Profile.Name FROM User "
        . "WHERE Name LIKE '%{$q}%' AND IsActive=true ORDER BY Name LIMIT 20"
    );
    $users = [];
    foreach (($r['records'] ?? []) as $u) {
        $users[] = [
            'id'      => $u['Id'] ?? null,
            'name'    => $u['Name'] ?? null,
            'email'   => $u['Email'] ?? null,
            'profile' => $u['Profile']['Name'] ?? null,
        ];
    }
    return ['total' => $r['totalSize'] ?? 0, 'users' => $users];
}

function sf_describe_object(array $args): array {
    $obj = preg_replace('/[^a-zA-Z0-9_]/', '', $args['object'] ?? 'Lead');
    $r = sf_api('GET', '/sobjects/' . $obj . '/describe');
    $fields = [];
    foreach (($r['fields'] ?? []) as $f) {
        $pv = $f['picklistValues'] ?? [];
        $fields[] = [
            'name'       => $f['name'],
            'label'      => $f['label'],
            'type'       => $f['type'],
            'custom'     => $f['custom'] ?? false,
            'updateable' => $f['updateable'] ?? false,
            'required'   => !($f['nillable'] ?? true) && !($f['defaultedOnCreate'] ?? false),
            'length'     => $f['length'] ?? null,
            'picklistValues' => $pv ? array_map(fn($p) => $p['value'],
                array_filter($pv, fn($p) => $p['active'] ?? false)) : null,
        ];
    }
    return ['object' => $obj, 'total' => count($fields), 'fields' => $fields];
}

function sf_soql_query(array $args): array {
    $query = $args['query'] ?? '';
    // Block destructive operations
    if (preg_match('/^\s*(INSERT|UPDATE|DELETE|UPSERT|MERGE)/i', $query)) {
        throw new Exception('Only SELECT queries are allowed via sf_soql_query. Use dedicated tools for write operations.');
    }
    $r = sf_soql($query);
    return [
        'totalSize' => $r['totalSize'] ?? 0,
        'done'      => $r['done'] ?? true,
        'records'   => $r['records'] ?? [],
    ];
}

function sf_search_contacts(array $args): array {
    $q   = sf_escape($args['query']);
    $lim = min((int)($args['limit'] ?? 10), 50);
    $r = sf_soql(
        "SELECT Id,FirstName,LastName,Email,Phone,Account.Name,Title,OwnerId,Owner.Name "
        . "FROM Contact WHERE Name LIKE '%{$q}%' OR Email LIKE '%{$q}%' "
        . "ORDER BY LastModifiedDate DESC LIMIT {$lim}"
    );
    $records = [];
    foreach (($r['records'] ?? []) as $x) {
        $records[] = [
            'id'      => $x['Id'] ?? null,
            'name'    => trim(($x['FirstName'] ?? '') . ' ' . ($x['LastName'] ?? '')),
            'email'   => $x['Email'] ?? null,
            'phone'   => $x['Phone'] ?? null,
            'account' => $x['Account']['Name'] ?? null,
            'title'   => $x['Title'] ?? null,
            'owner'   => $x['Owner']['Name'] ?? null,
        ];
    }
    return ['total' => $r['totalSize'] ?? 0, 'records' => $records];
}

function sf_search_accounts(array $args): array {
    $q   = sf_escape($args['query']);
    $lim = min((int)($args['limit'] ?? 10), 50);
    $r = sf_soql(
        "SELECT Id,Name,Industry,Website,Phone,BillingCity,BillingCountry,"
        . "NumberOfEmployees,OwnerId,Owner.Name "
        . "FROM Account WHERE Name LIKE '%{$q}%' "
        . "ORDER BY LastModifiedDate DESC LIMIT {$lim}"
    );
    $records = [];
    foreach (($r['records'] ?? []) as $x) {
        $records[] = [
            'id'        => $x['Id'] ?? null,
            'name'      => $x['Name'] ?? null,
            'industry'  => $x['Industry'] ?? null,
            'website'   => $x['Website'] ?? null,
            'phone'     => $x['Phone'] ?? null,
            'city'      => $x['BillingCity'] ?? null,
            'country'   => $x['BillingCountry'] ?? null,
            'employees' => $x['NumberOfEmployees'] ?? null,
            'owner'     => $x['Owner']['Name'] ?? null,
        ];
    }
    return ['total' => $r['totalSize'] ?? 0, 'records' => $records];
}

function sf_search_opportunities(array $args): array {
    $q   = sf_escape($args['query']);
    $lim = min((int)($args['limit'] ?? 10), 50);
    $r = sf_soql(
        "SELECT Id,Name,StageName,Amount,CloseDate,Account.Name,OwnerId,Owner.Name,"
        . "Probability,IsClosed,IsWon "
        . "FROM Opportunity WHERE Name LIKE '%{$q}%' OR Account.Name LIKE '%{$q}%' "
        . "ORDER BY LastModifiedDate DESC LIMIT {$lim}"
    );
    $records = [];
    foreach (($r['records'] ?? []) as $x) {
        $records[] = [
            'id'          => $x['Id'] ?? null,
            'name'        => $x['Name'] ?? null,
            'stage'       => $x['StageName'] ?? null,
            'amount'      => $x['Amount'] ?? null,
            'closeDate'   => $x['CloseDate'] ?? null,
            'account'     => $x['Account']['Name'] ?? null,
            'probability' => $x['Probability'] ?? null,
            'isClosed'    => $x['IsClosed'] ?? false,
            'isWon'       => $x['IsWon'] ?? false,
            'owner'       => $x['Owner']['Name'] ?? null,
        ];
    }
    return ['total' => $r['totalSize'] ?? 0, 'records' => $records];
}

// ─── Tool Registry ─────────────────────────────────────────────────────
$TOOLS = [
    'sf_search_leads' => [
        'description' => 'Search for leads by name, email, company, or phone. Returns matching lead records with key fields.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'query' => ['type' => 'string', 'description' => 'Search term (name, email, company, or phone)'],
                'limit' => ['type' => 'number', 'description' => 'Max results, 1-50 (default 10)'],
            ],
            'required' => ['query'],
        ],
    ],
    'sf_get_lead' => [
        'description' => 'Get full details of a single lead by its Salesforce ID.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'lead_id' => ['type' => 'string', 'description' => 'Salesforce Lead ID (e.g., 00Qxx...)'],
            ],
            'required' => ['lead_id'],
        ],
    ],
    'sf_create_lead' => [
        'description' => 'Create a new lead. Pass any valid Lead fields inside the "fields" object. LastName and Company are required.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'fields' => ['type' => 'object', 'description' => 'Lead fields to set. Must include LastName and Company. Use sf_describe_object to discover available fields.'],
            ],
            'required' => ['fields'],
        ],
    ],
    'sf_update_lead' => [
        'description' => 'Update fields on an existing lead. Pass only the fields you want to change.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'lead_id' => ['type' => 'string', 'description' => 'Salesforce Lead ID'],
                'fields'  => ['type' => 'object', 'description' => 'Fields to update (key-value pairs)'],
            ],
            'required' => ['lead_id', 'fields'],
        ],
    ],
    'sf_delete_lead' => [
        'description' => 'Delete a lead by ID. This action is permanent.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'lead_id' => ['type' => 'string', 'description' => 'Salesforce Lead ID to delete'],
            ],
            'required' => ['lead_id'],
        ],
    ],
    'sf_change_owner' => [
        'description' => 'Change the owner of a lead to a different Salesforce user.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'lead_id'      => ['type' => 'string', 'description' => 'Salesforce Lead ID'],
                'new_owner_id' => ['type' => 'string', 'description' => 'User ID of new owner (use sf_search_users to find)'],
            ],
            'required' => ['lead_id', 'new_owner_id'],
        ],
    ],
    'sf_log_activity' => [
        'description' => 'Log a task/activity on a lead (e.g., call, email, meeting note).',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'lead_id'       => ['type' => 'string', 'description' => 'Lead ID to associate the activity with'],
                'subject'       => ['type' => 'string', 'description' => 'Activity subject line'],
                'description'   => ['type' => 'string', 'description' => 'Activity details/notes'],
                'status'        => ['type' => 'string', 'description' => 'Status: Completed, Not Started, In Progress, etc. (default: Completed)'],
                'priority'      => ['type' => 'string', 'description' => 'Priority: High, Normal, Low (default: Normal)'],
                'activity_date' => ['type' => 'string', 'description' => 'Date in YYYY-MM-DD format (default: today)'],
            ],
            'required' => ['lead_id', 'subject'],
        ],
    ],
    'sf_search_users' => [
        'description' => 'Search active Salesforce users by name. Useful for finding user IDs for owner assignment.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'name' => ['type' => 'string', 'description' => 'Name to search for'],
            ],
            'required' => ['name'],
        ],
    ],
    'sf_describe_object' => [
        'description' => 'List all fields on a Salesforce object (Lead, Contact, Account, Opportunity, etc.). Shows field names, types, picklist values, and whether they are required or updateable.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'object' => ['type' => 'string', 'description' => 'Object API name (default: Lead). Examples: Lead, Contact, Account, Opportunity, Task'],
            ],
        ],
    ],
    'sf_soql_query' => [
        'description' => 'Run a read-only SOQL query against Salesforce. Only SELECT queries are allowed.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'query' => ['type' => 'string', 'description' => 'SOQL SELECT query string'],
            ],
            'required' => ['query'],
        ],
    ],
    'sf_search_contacts' => [
        'description' => 'Search for contacts by name or email.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'query' => ['type' => 'string', 'description' => 'Search term (name or email)'],
                'limit' => ['type' => 'number', 'description' => 'Max results, 1-50 (default 10)'],
            ],
            'required' => ['query'],
        ],
    ],
    'sf_search_accounts' => [
        'description' => 'Search for accounts by name.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'query' => ['type' => 'string', 'description' => 'Account name to search'],
                'limit' => ['type' => 'number', 'description' => 'Max results, 1-50 (default 10)'],
            ],
            'required' => ['query'],
        ],
    ],
    'sf_search_opportunities' => [
        'description' => 'Search for opportunities by name or account name.',
        'inputSchema' => [
            'type' => 'object',
            'properties' => [
                'query' => ['type' => 'string', 'description' => 'Opportunity or account name to search'],
                'limit' => ['type' => 'number', 'description' => 'Max results, 1-50 (default 10)'],
            ],
            'required' => ['query'],
        ],
    ],
];

// ─── MCP Request Handler ───────────────────────────────────────────────
function handle_mcp_request(array $req): ?array {
    global $TOOLS;
    $method = $req['method'] ?? '';
    $reqId  = $req['id'] ?? null;
    $params = $req['params'] ?? [];

    if ($method === 'initialize') {
        return [
            'jsonrpc' => '2.0',
            'id'      => $reqId,
            'result'  => [
                'protocolVersion' => '2025-03-26',
                'capabilities'    => ['tools' => (object)[]],
                'serverInfo'      => [
                    'name'    => 'salesforce-crm-mcp',
                    'version' => '1.0.0',
                ],
            ],
        ];
    }

    if ($method === 'notifications/initialized') return null;

    if ($method === 'tools/list') {
        $list = [];
        foreach ($TOOLS as $name => $spec) {
            $list[] = [
                'name'        => $name,
                'description' => $spec['description'],
                'inputSchema' => $spec['inputSchema'],
            ];
        }
        return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => ['tools' => $list]];
    }

    if ($method === 'tools/call') {
        $toolName = $params['name'] ?? '';
        $toolArgs = $params['arguments'] ?? [];
        if (!isset($TOOLS[$toolName]) || !function_exists($toolName)) {
            return [
                'jsonrpc' => '2.0', 'id' => $reqId,
                'result'  => [
                    'content' => [['type' => 'text', 'text' => "Unknown tool: $toolName. Use tools/list to see available tools."]],
                    'isError' => true,
                ],
            ];
        }
        try {
            $result = $toolName($toolArgs);
            return [
                'jsonrpc' => '2.0', 'id' => $reqId,
                'result'  => ['content' => [['type' => 'text', 'text' => json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)]]],
            ];
        } catch (Exception $e) {
            return [
                'jsonrpc' => '2.0', 'id' => $reqId,
                'result'  => ['content' => [['type' => 'text', 'text' => 'Error: ' . $e->getMessage()]], 'isError' => true],
            ];
        }
    }

    if ($method === 'ping')                     return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => (object)[]];
    if ($method === 'resources/list')            return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => ['resources' => []]];
    if ($method === 'resources/templates/list')  return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => ['resourceTemplates' => []]];
    if ($method === 'prompts/list')              return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => ['prompts' => []]];
    if ($method === 'completion/complete')       return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => ['completion' => ['values' => []]]];
    if ($method === 'logging/setLevel')          return ['jsonrpc' => '2.0', 'id' => $reqId, 'result' => (object)[]];

    return ['jsonrpc' => '2.0', 'id' => $reqId, 'error' => ['code' => -32601, 'message' => "Method not found: $method"]];
}

// ─── Main Request Routing ──────────────────────────────────────────────
$requestUri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// Health / status check
if ($_SERVER['REQUEST_METHOD'] === 'GET' && (
    $requestUri === '/health' || str_ends_with($requestUri, '/health') ||
    (str_contains($requestUri, 'mcp.php') && isset($_GET['health']))
)) {
    header('Content-Type: application/json');
    $auth = get_auth_method();
    echo json_encode([
        'status'      => $auth !== 'none' ? 'ok' : 'unconfigured',
        'service'     => 'salesforce-crm-mcp',
        'version'     => '1.0.0',
        'auth_method' => $auth,
        'api_version' => API_VERSION,
    ]);
    exit;
}

// Setup check
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['setup'])) {
    header('Content-Type: application/json');
    $auth   = get_auth_method();
    $checks = ['auth_configured' => $auth !== 'none', 'auth_method' => $auth];
    if ($auth !== 'none') {
        try {
            $session = sf_ensure_session();
            $checks['salesforce_connected'] = true;
            $checks['instance_url'] = $session['instance_url'];
        } catch (Exception $e) {
            $checks['salesforce_connected'] = false;
            $checks['error'] = $e->getMessage();
        }
    }
    echo json_encode($checks, JSON_PRETTY_PRINT);
    exit;
}

// MCP POST endpoint
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $input = file_get_contents('php://input');
    $req   = json_decode($input, true);

    if (!$req) {
        header('Content-Type: application/json');
        http_response_code(400);
        echo json_encode(['jsonrpc' => '2.0', 'error' => ['code' => -32700, 'message' => 'Parse error']]);
        exit;
    }

    $sessionId = $_SERVER['HTTP_MCP_SESSION_ID'] ?? null;
    if (!$sessionId && ($req['method'] ?? '') === 'initialize') {
        $sessionId = 'mcp-sf-' . bin2hex(random_bytes(16));
    }

    $response = handle_mcp_request($req);

    if ($response === null) {
        http_response_code(202);
        if ($sessionId) header("Mcp-Session-Id: $sessionId");
        exit;
    }

    header('Content-Type: application/json');
    if ($sessionId) header("Mcp-Session-Id: $sessionId");
    echo json_encode($response);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'DELETE') { http_response_code(200); exit; }

// Default GET response
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    header('Content-Type: application/json');
    echo json_encode([
        'name'         => 'Salesforce CRM MCP Server',
        'version'      => '1.0.0',
        'description'  => 'MCP server for Salesforce CRM — search, create, update leads, contacts, accounts, opportunities, and more.',
        'mcp_endpoint' => 'POST to this URL',
        'health'       => 'GET ?health',
        'setup'        => 'GET ?setup',
    ]);
    exit;
}

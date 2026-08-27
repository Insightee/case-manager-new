# External integrations and remote MCP

Read-only machine access to authorised InsighteCase data for partner apps and AI agents.

## Architecture

- External callers never connect to the database.
- REST (`/api/v1/integrations/...`) and MCP (`/mcp`) call `app/services/integration/*`.
- Access requires an integration client, hashed client secret, explicit scopes, and explicit case grants.
- Responses are field-masked (no child full names, DOB, addresses, GPS, report HTML, or tokens in audit payloads).

## Enable

Set on the Railway API service:

```bash
INTEGRATION_API_ENABLED=true
MCP_ENABLED=true
INTEGRATION_JWT_SECRET_KEY=your-integration-jwt-secret
INTEGRATION_ACCESS_TOKEN_MINUTES=15
```

Restart the API after migration (`i1integr2api3layer` is applied by the normal production migrate path).

The FastAPI lifespan starts the MCP Streamable HTTP session manager; without `MCP_ENABLED=true` the `/mcp` route is not mounted.

## Create a client (admin)

As a user with `user.manage` (e.g. SUPER_ADMIN):

```http
POST /api/v1/admin/integration-clients
Authorization: Bearer <human-access-token>
Content-Type: application/json

{
  "name": "Partner reporting agent",
  "scopes": ["cases:read", "reports:read", "sessions:summarize", "reporting:pending", "ops:summary"],
  "case_ids": [101, 102]
}
```

Store `client_id` and `client_secret` from the response immediately (secret is shown once).

## Obtain a token

```http
POST /api/v1/integrations/oauth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

## Example MCP connection (placeholders only)

```json
{
  "mcpServers": {
    "insightcase": {
      "url": "https://YOUR_API_BASE/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_INTEGRATION_ACCESS_TOKEN"
      }
    }
  }
}
```

Issue the access token via the token endpoint above; do not put the long-lived client secret in MCP host config when a short-lived token can be used.

## Scopes

| Scope | Access |
|---|---|
| `cases:read` | Masked case list/detail |
| `reports:read` | Masked report list/detail |
| `sessions:summarize` | Session aggregates for a granted case |
| `reporting:pending` | Under-review / missing monthly items |
| `ops:summary` | Anonymised counts only |

## MCP tools (read-only)

- `list_authorised_reports`
- `get_report`
- `get_case_summary`
- `get_session_summary`
- `list_pending_reporting`
- `get_anonymised_ops_summary`

No write, approve, delete, or status-changing tools are exposed in this phase.

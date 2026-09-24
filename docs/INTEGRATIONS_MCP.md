# External integrations and remote MCP

Machine access to authorised InsighteCase data for partner apps and AI agents. Reads are masked. Writes are structured signals for review and never complete a report or replace therapist notes.

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

## Create a client (super admin)

From **Admin → Integrations**, or as a user with `admin.override`:

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
| `cases:write` | Submit a structured case signal (`pending_review`) |
| `sessions:write` | Submit a structured session signal (`pending_review`) |
| `goals:read` | Goal and strategy identifiers for granted cases. Paged. Strategy rows use `linked_goal_card_id`, not `goals[].goal_id` |
| `goals:write` | Submit a structured goal signal (`pending_review`) |
| `iep:read` | IEP framework identifiers and counts |
| `profiles:read` | Therapist listing fields (name, bio, qualifications, certificates, services, status). Login email is not included |
| `profiles:write` | Create a Pending listing for an existing therapist. The key cannot approve, pause, or revive a deleted listing |

Reports, IEP, pending reporting, and operations stay read-only. A write never sets a report to complete. Profile create does not change leave, TDS, clinical notes, or report status.

Access token life is per key: 15 minutes, 1 hour, 8 hours, or 24 hours. API key validity is 30 days, 90 days, 1 year, or no expiry.

## Therapist profiles

```http
GET /api/v1/integrations/v1/therapist-profiles?status=APPROVED
Authorization: Bearer <access-token>
```

```http
POST /api/v1/integrations/v1/therapist-profiles
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "user_id": 12,
  "display_name": "Asha Menon",
  "short_bio": "Supports participation at home and school.",
  "services_offered": ["homecare"]
}
```

`user_id` must already be an active therapist. A second profile is refused, including a soft-deleted listing. The created status is always `PENDING`. `APPROVED`, `PAUSED`, and `DELETED` are refused. Leave balances, TDS, approval snapshots, and login email are not returned.

```http
GET /api/v1/integrations/v1/goals?page=1&page_size=25
Authorization: Bearer <access-token>
```

`goals` and `strategies` are each `{ items, total, page, page_size, pages }`. `GET /api/v1/integrations/v1/iep` returns `plans` in that same page shape.

## MCP tools

- `list_authorised_reports`
- `get_report`
- `get_case_summary`
- `get_session_summary`
- `list_pending_reporting`
- `get_anonymised_ops_summary`
- `list_goal_framework`
- `list_iep_framework`
- `list_therapist_profiles` (`profiles:read`)
- `create_therapist_profile` (`profiles:write`)

Clinical MCP tools stay read-only. `create_therapist_profile` is the profile-listing exception and still cannot complete a report. Turn **Allow MCP** off on a key to refuse these tools. Webhooks are configured in the super admin Integrations screen and store a signing secret once.

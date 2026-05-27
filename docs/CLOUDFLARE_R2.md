# Cloudflare R2 for InsightCase

Production uploads use **R2** via S3-compatible API keys (not the `cfat_` dashboard API token).

## What each credential is for

| Credential | Example shape | Use |
|------------|---------------|-----|
| **Account API token** | `cfat_…` | Cloudflare dashboard API, Workers, DNS automation — **not** `R2_ACCESS_KEY_ID` |
| **R2 access key ID** | 32 hex chars | `R2_ACCESS_KEY_ID` on Railway |
| **R2 secret access key** | 64 hex chars | `R2_SECRET_ACCESS_KEY` on Railway |

Create R2 keys: Cloudflare → **R2** → **Manage R2 API tokens** → Create API token (Object Read & Write on bucket `insightecase`).

## Account / bucket (this project)

| Item | Value |
|------|--------|
| Account ID | `0409ea66ef188ae9783c5e9aa7af9445` |
| Bucket | `insightecase` |
| Endpoint | `https://0409ea66ef188ae9783c5e9aa7af9445.r2.cloudflarestorage.com` |
| Object key prefix | `insightcase/production/…` (from `STORAGE_PREFIX` + `STORAGE_ENVIRONMENT`) |

## Railway API service variables

Set on service **case-manager-new** (project **truthful-blessing**, id `ead85fb6-1826-4eed-bad9-2513e89c4854`):

```
STORAGE_PROVIDER=r2
STORAGE_PREFIX=insightcase
STORAGE_ENVIRONMENT=production
R2_ACCOUNT_ID=0409ea66ef188ae9783c5e9aa7af9445
R2_BUCKET_NAME=insightecase
R2_ENDPOINT_URL=https://0409ea66ef188ae9783c5e9aa7af9445.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<32-char from R2 API token>
R2_SECRET_ACCESS_KEY=<secret from R2 API token>
```

Remove legacy/wrong names if present: `SMTP_USERNAME` → use `SMTP_USER`; `EMAIL_FROM_DEFAULT` → use `SMTP_FROM_EMAIL`.

After saving variables, **Redeploy** the API service.

## Verify locally

```bash
cd backend
export R2_ACCESS_KEY_ID='...'
export R2_SECRET_ACCESS_KEY='...'
export R2_ENDPOINT_URL='https://0409ea66ef188ae9783c5e9aa7af9445.r2.cloudflarestorage.com'
export R2_BUCKET_NAME='insightecase'
python3 scripts/r2_smoke_test.py
```

## Push vars via Railway (project token)

1. Railway → project **truthful-blessing** → **Settings** → **Tokens** → create token (do not paste in chat).
2. Run:

```bash
cd backend
export RAILWAY_PROJECT_TOKEN='...'
export R2_ACCESS_KEY_ID='...'
export R2_SECRET_ACCESS_KEY='...'
python3 scripts/railway_set_vars_graphql.py
```

## Security

- Rotate any keys or tokens shared in chat or tickets.
- Never commit `cfat_`, R2 secrets, or Railway tokens to git.

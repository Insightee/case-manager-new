# InsightCase documentation index

Central index for all repo documentation. Start here or from [AGENTS.md](../AGENTS.md) for agent/onboarding rules.

## Getting started

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Repo overview, local dev quick start |
| [../backend/README.md](../backend/README.md) | API, roles, migrations, backend commands |
| [../frontend/README.md](../frontend/README.md) | Vite app, build, E2E |
| [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) | **All env vars** — local, Railway, Vercel, CI |
| [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md) | Delivery, RBAC, billing, deploy checklists for agents |

## Deploy & infrastructure

| Doc | Purpose |
|-----|---------|
| [DEPLOY.md](./DEPLOY.md) | End-to-end deploy checklist |
| [RAILWAY_VERCEL.md](./RAILWAY_VERCEL.md) | Railway API + Vercel frontend pairing, tokens, CORS |
| [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) | Pre-release verification |
| [CLOUDFLARE_R2.md](./CLOUDFLARE_R2.md) | R2 object storage for production uploads |
| [EMAIL_DNS.md](./EMAIL_DNS.md) | ZeptoMail, SMTP, DNS records |
| [STAGING_SMOKE.md](./STAGING_SMOKE.md) | Post-import session log smoke test |

### Env templates (in repo)

| File | Purpose |
|------|---------|
| [../backend/.env.example](../backend/.env.example) | Local backend |
| [../backend/env.railway.example](../backend/env.railway.example) | Railway production API |
| [../frontend/.env.example](../frontend/.env.example) | Local frontend |
| [../frontend/vercel-env.example](../frontend/vercel-env.example) | Vercel production/preview |

## Architecture & product

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System overview, components, data flow |
| [billing-architecture.md](./billing-architecture.md) | Invoices, payouts, billing modes |
| [RBAC_SCOPE.md](./RBAC_SCOPE.md) | Roles, permissions, module access |
| [REVIEW_ROLE_MATRIX.md](./REVIEW_ROLE_MATRIX.md) | Role review matrix |
| [ROLE_MODEL_PHASES.md](./ROLE_MODEL_PHASES.md) | Role model rollout phases |
| [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md) | Product roadmap |
| [PILOT_RELEASE_SCOPE.md](./PILOT_RELEASE_SCOPE.md) | Pilot release boundaries |
| [BOARD_ONE_PAGER.md](./BOARD_ONE_PAGER.md) | Executive one-pager |

## Support hub & HR (recent)

| Doc | Purpose |
|-----|---------|
| [HANDOVER_SUPPORT_HR.md](./HANDOVER_SUPPORT_HR.md) | Support desk, HR dashboard, HR reports handover |
| [adr/adr-0001-support-hub-access-scopes.md](./adr/adr-0001-support-hub-access-scopes.md) | ADR: support hub access scopes |

## Data & operations

| Doc | Purpose |
|-----|---------|
| [DATA_IMPORT.md](./DATA_IMPORT.md) | Production bulk import (therapists, families, cases) |
| [import-templates/](./import-templates/) | Example CSV templates for import |

## Quality, scale & review

| Doc | Purpose |
|-----|---------|
| [SCALING_P1_IMPLEMENTATION.md](./SCALING_P1_IMPLEMENTATION.md) | P1 scaling work |
| [SCALABILITY_REVIEW.md](./SCALABILITY_REVIEW.md) | Scalability review notes |
| [TEST_GAP_BACKLOG.md](./TEST_GAP_BACKLOG.md) | Test coverage gaps |
| [REVIEW_FINDINGS.md](./REVIEW_FINDINGS.md) | Review findings log |
| [reports/production-e2e-latest.md](./reports/production-e2e-latest.md) | Latest production E2E report |
| [reports/email-delivery-diagnosis.md](./reports/email-delivery-diagnosis.md) | Email delivery diagnosis |

## Frontend UX

| Doc | Purpose |
|-----|---------|
| [../frontend/docs/admin-mobile-ux.md](../frontend/docs/admin-mobile-ux.md) | Admin portal mobile UX rules |

## Agent memory

| Doc | Purpose |
|-----|---------|
| [../AGENTS.md](../AGENTS.md) | Learned preferences, deploy split, local dev facts |

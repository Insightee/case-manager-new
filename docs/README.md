# InsighteCase documentation index

Central index for all repo documentation. Start here or from [AGENTS.md](../AGENTS.md) for agent/onboarding rules.

## Getting started

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Repo overview, local dev quick start |
| [../backend/README.md](../backend/README.md) | API, roles, migrations, backend commands |
| [../frontend/README.md](../frontend/README.md) | Vite app, build, E2E |
| [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) | **All env vars** — local, Railway, Vercel, CI |
| [INTEGRATIONS_MCP.md](./INTEGRATIONS_MCP.md) | External integration API + remote MCP (read-only) |
| [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md) | Delivery, RBAC, billing, deploy checklists for agents |
| [LOOP_SYSTEM.md](./LOOP_SYSTEM.md) | **Grind loops** — bounded initiative execution, interlocks, work packages |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | **Team workflow** — PRs, pre-push, hooks, release |
| [../CHANGELOG.md](../CHANGELOG.md) | **Change log** — `[Unreleased]` + dated releases |
| [TEAM_OWNERSHIP.md](./TEAM_OWNERSHIP.md) | Area owners, CODEOWNERS |
| [GITHUB_SETUP.md](./GITHUB_SETUP.md) | Branch protection and required CI checks |

## Deploy & infrastructure

| Doc | Purpose |
|-----|---------|
| [DEPLOY.md](./DEPLOY.md) | End-to-end deploy checklist |
| [RAILWAY_VERCEL.md](./RAILWAY_VERCEL.md) | Railway API + Vercel frontend pairing, tokens, CORS |
| [Cursor_Handover_Production_Readonly_Postgres.md](./Cursor_Handover_Production_Readonly_Postgres.md) | Prod SELECT-only Postgres role for cutover / finance reads |
| [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) | Pre-release verification |
| [FINANCE_CUTOVER_RUNBOOK.md](./FINANCE_CUTOVER_RUNBOOK.md) | **Finance cutover** — staged flag enablement (Loops C–E) |
| [FINANCE_SNAPSHOT_PROD_CUTOVER.md](./FINANCE_SNAPSHOT_PROD_CUTOVER.md) | **Stage 1 snapshot on insighte.org** — read-only prod enablement |
| [finance/outgoing_calendar_day_clamp.md](./finance/outgoing_calendar_day_clamp.md) | Outgoing Shadow/B2B calendar-day clamp — shared client/therapist days, freeze/replay, post-merge arrears |
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
| [Cursor_Handover_Clinical_Reports_Structure.md](./Cursor_Handover_Clinical_Reports_Structure.md) | CTO handover: clinical reports schema, UI, generation, storage |
| [Cursor_Handover_Admin_Operational_Reports.md](./Cursor_Handover_Admin_Operational_Reports.md) | CTO handover: Finance / HR / CRM admin Reports (exports) |
| [billing-architecture.md](./billing-architecture.md) | Invoices, payouts, billing modes |
| [Cursor_Handover_Finance_Dashboard_Stage1.md](./Cursor_Handover_Finance_Dashboard_Stage1.md) | Stage 1 read-only Finance Control Tower handover + verdict |
| [Cursor_Handover_Finance_Dashboard_Stage1_Staging_Acceptance.md](./Cursor_Handover_Finance_Dashboard_Stage1_Staging_Acceptance.md) | Gate 1 local/CI staging-equivalent acceptance |
| [Cursor_Handover_Finance_Dashboard_Stage2.md](./Cursor_Handover_Finance_Dashboard_Stage2.md) | Stage 2 engine-aware client billing + Forest Light reskin |
| [Cursor_Handover_Finance_Merge_Local_Runbook.md](./Cursor_Handover_Finance_Merge_Local_Runbook.md) | Post-merge local runbook results (flags off/on) |
| [finance_control_tower_stage1_human_uat_script.md](./finance_control_tower_stage1_human_uat_script.md) | Timed human finance UAT script (blank results) |
| [RBAC_SCOPE.md](./RBAC_SCOPE.md) | Roles, permissions, module access |
| [REVIEW_ROLE_MATRIX.md](./REVIEW_ROLE_MATRIX.md) | Role review matrix |
| [ROLE_MODEL_PHASES.md](./ROLE_MODEL_PHASES.md) | Role model rollout phases |
| [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md) | Product roadmap |
| [PILOT_RELEASE_SCOPE.md](./PILOT_RELEASE_SCOPE.md) | Pilot release boundaries |
| [BOARD_ONE_PAGER.md](./BOARD_ONE_PAGER.md) | Executive one-pager |

## Initiatives in flight

Executed as bounded work packages — see [LOOP_SYSTEM.md](./LOOP_SYSTEM.md).

| Doc | Purpose |
|-----|---------|
| [initiatives/finance-dashboard.md](./initiatives/finance-dashboard.md) | **Finance dashboard initiative** — intent, non-negotiables, success criteria |
| [plans/finance-dashboard-revamp.md](./plans/finance-dashboard-revamp.md) | Work packages FIN-00 to FIN-12, status board, `baseline_sha` |
| [plans/finance-open-questions.md](./plans/finance-open-questions.md) | Escalation register — blocks packages until answered |
| [Cursor_Handover_Finance_Module_Build_Readiness.md](./Cursor_Handover_Finance_Module_Build_Readiness.md) | Prior finance audit — **verify per section before relying on it** |

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
| [PARENT_CLIENT_PORTAL_GUIDE.md](./PARENT_CLIENT_PORTAL_GUIDE.md) | **Parent / guardian guide** — client portal navigation and features |
| [THERAPIST_PORTAL_GUIDE.md](./THERAPIST_PORTAL_GUIDE.md) | **Therapist guide** (Markdown source) — portal navigation and daily workflows |
| [THERAPIST_PORTAL_GUIDE.pdf](./THERAPIST_PORTAL_GUIDE.pdf) | **Therapist guide (PDF)** — share with therapists; regenerate via `scripts/generate-therapist-guide-pdf.sh` |
| [../frontend/docs/admin-mobile-ux.md](../frontend/docs/admin-mobile-ux.md) | Admin portal mobile UX rules |

## Agent memory

| Doc | Purpose |
|-----|---------|
| [../AGENTS.md](../AGENTS.md) | Learned preferences, deploy split, local dev facts |

hello
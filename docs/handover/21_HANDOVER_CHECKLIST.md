# 21 — Handover Checklist

Use when transferring ownership from outgoing to incoming developers.

---

## REPOSITORY

- [ ] Repository access confirmed for all engineers (GitHub org `Insightee` or successor)  
- [ ] Organization admin role assigned to at least two people  
- [ ] Default branch `main` and protection rules documented ([GITHUB_SETUP.md](../GITHUB_SETUP.md))  
- [ ] Required CI checks understood (`backend`, `frontend`, `vercel-monorepo-build`, `postgres-migration-proof`, `contributor-guards`)  
- [ ] Retired Vercel Git apps disconnected from repo  

---

## DEPLOYMENT

- [ ] Railway project access transferred (`case-manager-new` API service)  
- [ ] Railway Postgres + Redis plugin access documented  
- [ ] Vercel team `insightes-projects` access — project **`frontend` only**  
- [ ] Production domains documented (`www.insighte.org`, Railway public URL)  
- [ ] Staging/testing URLs and flag matrix — **fill in if applicable**  
- [ ] Auto-deploy on merge verified or documented as manual  

---

## DATABASE

- [ ] Production Postgres connection process (Railway dashboard / readonly role doc)  
- [ ] Migration procedure rehearsed (`migrate_production.py`, single Alembic head)  
- [ ] Backup procedure — **UNKNOWN — VERIFY WITH TEAM** (Railway backups / PITR)  
- [ ] Finance cutover state documented (`ENABLE_BILLING`, ledger writes, cutover complete flag)  

---

## SECRETS

- [ ] JWT secrets rotated or rotation schedule agreed  
- [ ] SMTP ZeptoMail token in Railway only  
- [ ] R2 API keys transferred  
- [ ] Integration/Zoho/Razorpay keys inventory — **VERIFY WITH TEAM**  
- [ ] `RAILWAY_API_TOKEN` / `VERCEL_TOKEN` custodians named  
- [ ] No secrets in Git history (scan if concerned)  
- [ ] Password manager or vault entries for all of the above  

---

## DOCUMENTATION

- [ ] Incoming dev read [00_MASTER_HANDOVER.md](./00_MASTER_HANDOVER.md)  
- [ ] [04_LOCAL_DEVELOPMENT.md](./04_LOCAL_DEVELOPMENT.md) completed successfully on incoming machine  
- [ ] [14_DEPLOYMENT.md](./14_DEPLOYMENT.md) walkthrough done  
- [ ] [11_BUSINESS_LOGIC.md](./11_BUSINESS_LOGIC.md) + finance runbooks for finance owner  
- [ ] [DOCUMENTATION_GAPS.md](./DOCUMENTATION_GAPS.md) items assigned owners  

---

## KNOWLEDGE TRANSFER

- [ ] Architecture walkthrough (30–60 min) — portals + case model  
- [ ] RBAC demo on People → Staff access editor  
- [ ] Therapist day-in-the-life: session → log → approve → parent view  
- [ ] Finance flags and what is **not** live in production  
- [ ] Support hub + incident sensitivity briefing  
- [ ] Incoming dev deployed a **preview** or staging build **OR** documented why not  
- [ ] Incoming dev merged a trivial docs/chore PR through CI  
- [ ] Incoming dev diagnosed one issue using [17_TROUBLESHOOTING.md](./17_TROUBLESHOOTING.md)  

---

## OUTGOING DEVELOPER SIGN-OFF

| Item | Outgoing | Incoming | Date |
|------|----------|----------|------|
| Local dev verified | | | |
| Production access verified | | | |
| Secrets transferred | | | |
| Walkthrough complete | | | |

---

## POST-HANDOVER FIRST WEEK (incoming)

1. Run full test suite and note failures.  
2. Read OpenAPI `/docs` on staging or local.  
3. Confirm `GET /health` on production after any env change.  
4. Do not enable `BILLING_LEDGER_WRITES` or `PAYOUT_RELEASE_ENABLED` without finance sign-off.

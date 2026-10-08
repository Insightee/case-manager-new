# Agent skills (Cursor)

Cursor and Cursor cloud agents load each `<name>/SKILL.md` on demand. Index:

| Skill | Use when |
|-------|----------|
| `cross-portal-impact` | Before implementing any fix/feature: parent + therapist + admin impact and risk table in the PR |
| `diagnosing-bugs` | Debug / root cause ("ce-debug"): red-capable repro first |
| `tdd` | Test-first work and the verification gate before "done" / PR |
| `code-review` | Reviewing a branch or PR for bugs and regressions (report-only) |
| `security-review` | Security review / security report, IDOR across portals |
| `migration-safety` | Any Alembic/model change |
| `ui-consistency` | Any UI change: one design system, reuse components |
| `mobile-responsive-qa` | Mobile/PWA layout rules and 375/390px QA |
| `tables-and-reports` | Tables, exports, PDFs, totals, IST dates, ₹ |
| `token-efficiency` | Every task: targeted search, scoped tests, no log dumps |

Repo rules still win: no pushes to `main`, PRs only after `./scripts/run-ci-parity-checks.sh` and `./scripts/pre-push-check.sh` pass, never merge or deploy without the owner. Licences and sources: `THIRD_PARTY_NOTICES.md`.

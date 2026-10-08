---
name: diagnosing-bugs
description: Root-cause debugging loop (the "ce-debug" workflow) for InsighteCase. Use when asked to "debug", "diagnose", "investigate", "find the root cause", or when something is broken, throwing, failing, slow or only fails in production (500s, failed submits, wrong totals, a portal-specific bug). Builds a red-capable repro before any fix.
license: MIT (Matt Pocock); see ../THIRD_PARTY_NOTICES.md
---

# Diagnosing Bugs

A discipline for hard bugs. Skip phases only when explicitly justified, and say why.

Before exploring, read `AGENTS.md`, `docs/ARCHITECTURE.md` and any ADR in `docs/adr/` for the area you touch. Use the `token-efficiency` skill: `rg` for the error string first, then read only the files on the code path.

## Guardrails (InsighteCase)

- **Redact every secret.** Write `<REDACTED>` for tokens, cookies, `DATABASE_URL`, passwords. Use env vars in commands so credentials never appear in output you show.
- **Production is read-only to you.** Use existing logs, Sentry-style traces or the owner's screenshots. Never add production instrumentation, change Railway/Vercel env, run SQL writes, restart services, or deploy. If you need any of that, stop and ask the owner.
- **Reproduce locally**: backend `cd backend && python3 -m pytest app/tests/<file>::<test> -q`, or `./scripts/grind-check.sh backend <selector>`; frontend via `npm run dev` + the dev API (`.cursor/environment.json`). Seed with `python3 -m app.seed.demo_seed`.
- **Check all three portals.** The same root cause usually hits parent, therapist and admin paths differently (see `cross-portal-impact`).

## Phase 1: Build a feedback loop

**This is the skill.** With a tight pass/fail signal that goes red on *this* bug, you will find the cause. Without one, staring at code will not save you. Spend disproportionate effort here.

Ways to build one, roughly in this order:
1. **Failing pytest** at whatever seam reaches the bug (API test via the FastAPI test client is usually best here).
2. **curl / HTTP script** against the local API.
3. **CLI invocation** with a fixture input, diffing output against a known-good snapshot.
4. **Headless browser script** (Playwright, `frontend/e2e/`) asserting on DOM, console or network.
5. **Replay a captured payload** (redacted request body from logs) through the code path.
6. **Throwaway harness**: one service, mocked externals, one function call.
7. **Property/fuzz loop** for "sometimes wrong" output.
8. **Bisection harness**: `git bisect run` with the loop when it worked at a known commit.
9. **Differential loop**: same input through old vs new version and diff.

Tighten the loop: faster (narrow test scope), sharper (assert the exact symptom), deterministic (freeze time with an explicit IST date, seed RNG, no network). Hard-coded calendar dates have broken this suite before; use relative dates.

**Non-deterministic bugs:** aim for a higher reproduction rate (loop 100x, add stress) rather than a clean repro.

**If you genuinely cannot build a loop:** stop and say so. List what you tried. Ask the owner for a redacted artefact (log lines, screenshot with timestamp, HAR) or access. Do not hypothesise without a loop.

**Done when** you can name one command you have already run that is red-capable (asserts the user's exact symptom), deterministic, fast, and runnable unattended.

## Phase 2: Reproduce and minimise

Run the loop and watch it go red. Confirm it is the failure the user described, not a nearby one. Then cut inputs, callers, config and data one at a time until every remaining element is load-bearing.

## Phase 3: Hypothesise

Write **3-5 ranked, falsifiable hypotheses** before testing any: "If X is the cause, changing Y makes the bug disappear." Put the ranked list in your plan / PR description. Do not block on feedback if the owner is away.

## Phase 4: Instrument

Each probe maps to one hypothesis; change one variable at a time. Prefer a debugger/REPL, then targeted logs. Tag every debug log with a unique prefix such as `[DEBUG-a4f2]` so cleanup is one `rg`. For performance, measure a baseline first (timing harness, `EXPLAIN`, query count), then bisect.

## Phase 5: Fix and regression test

Write the regression test **before** the fix, at a seam that exercises the real bug pattern. If no correct seam exists, that is a finding: note it in the PR.

1. Turn the minimised repro into a failing test. 2. Watch it fail. 3. Apply the smallest root-cause fix. 4. Watch it pass. 5. Re-run the original Phase 1 loop.

## Phase 6: Cleanup and verify

- [ ] Original repro no longer reproduces
- [ ] Regression test passes (or missing seam documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`rg "\[DEBUG-"`)
- [ ] Throwaway scripts deleted
- [ ] `./scripts/run-ci-parity-checks.sh` green before opening the PR (single Alembic head, full pytest, frontend build)
- [ ] The confirmed hypothesis and the cross-portal impact are written in the PR description

---
Adapted from mattpocock/skills `skills/engineering/diagnosing-bugs` (commit f3fc5632f401), https://github.com/mattpocock/skills. MIT License, Copyright (c) 2026 Matt Pocock. Full license text: `../THIRD_PARTY_NOTICES.md`.
Changes: added InsighteCase guardrails and commands; removed the human-in-the-loop script (cloud agents run unattended) and the "add temporary production instrumentation" option (production is read-only to agents); added the CI-parity gate.

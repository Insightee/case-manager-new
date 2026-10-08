---
name: token-efficiency
description: Work cheaply and fast in the InsighteCase repo. Use at the start of every task and whenever you are about to read many files, run the full test suite, paste logs, or write a long plan. Targeted search, scoped tests, short plans, no log dumps.
---

# Token Efficiency (InsighteCase)

The repo is large (142+ migrations, 1,200+ backend tests, three portals). Spend tokens on the code path that matters.

## Finding code

- **Search, don't browse.** Start with `rg -n "<error text|route|function>" backend/app frontend/src` (add `-g '!*.test.*'`, `-g '!node_modules'`). Use `rg -l` to list files, then read only those.
- Read **ranges**, not whole files: jump to the function from the `rg` line number. Big files (`frontend/src/index.css`, large page components, `postgres_migration_proof_registry.py`) are never read top to bottom.
- Trace one path: route (`backend/app/api/v1/`) -> service (`backend/app/services/`) -> model -> frontend caller (`rg` the endpoint path in `frontend/src`). Stop when the path is complete.
- Use the docs index (`docs/README.md`, `AGENTS.md`) to find the one relevant doc instead of opening many.
- Do not re-read a file you already read unless it changed.

## Running checks

- Inner loop: the narrowest test. `./scripts/grind-check.sh backend app/tests/test_x.py -k name`, or `python3 -m pytest app/tests/test_x.py::test_y -q`. Frontend: `./scripts/grind-check.sh frontend`.
- Use `-q --tb=line` (or `--tb=short`) and `-x` while iterating.
- Run the full gate (`./scripts/run-ci-parity-checks.sh`) **once** when the change is complete, and again only if code changed after it. Do not re-run the full suite to "double check".
- If a command is slow, run it in the background and do other reading meanwhile.

## Output and logs

- Never paste full logs, full diffs or full test output. Quote the failing test names and the 5-20 lines that carry the signal. Summaries: `1210 passed, 24 skipped, 0 failed`.
- Pipe long output to a file and `rg` it: `cmd > /tmp/out.txt 2>&1; rg -n "FAILED|Error" /tmp/out.txt`.
- Redact secrets in anything you show.

## Plans and messages

- Plans are short: goal, files to touch, steps, tests, risks (use the `cross-portal-impact` table instead of prose). No restating the request.
- PR descriptions: what changed, why, cross-portal table, test summary. No narrative of everything you tried.
- Ask one precise question when blocked instead of exploring blindly.

## Models (from AGENTS.md)

Prefer Composer / Grok-class models for exploration, subagents and browser checks. Use heavier reasoning models only when the owner picks one or the task truly needs deep multi-file reasoning. Parallel read-only subagents are fine for independent areas; give each a narrow brief.

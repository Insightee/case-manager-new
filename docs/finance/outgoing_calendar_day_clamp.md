# Outgoing calendar-day clamp

Finance-safe bound so an out-of-month approved-log date cannot be read as a
pay-month day (for example 3 July → 3 days while computing June).

**This is not payout-only.** `calendar_days_for_segment` feeds therapist pay
(`predicted_subtotal_inr`) and client gross (`client_case_gross_inr` via the
same `build_cycle_segments`). Ledger and composer reuse that gross.
Receivables and payables both move. Finance must sign both before merge.

## What `last_log` already means

Do not invent a “log every payable day” rule. Shadow/B2B ongoing segments still
pay start-through-30 with no last-log bound.

| Name in code | Meaning |
| --- | --- |
| `segment.last_log` / `first_log` | `MAX`/`MIN` of `sessions.scheduled_date` **in this billing month**, joined to a daily log with `approval_status=APPROVED` and `transition_id IS NULL` |
| `_last_approved_log_for_therapist` (`last_approved_ever`) | Same evidence type, **all-time** |
| Not used | Session completed clock, scheduled-without-log, attendance enum, child-absent rows |

Outgoing replacement end is already `last_approved_ever or last_log`. The clamp
only stops that date being interpreted in the wrong month. `seg_start` is
unchanged.

## Live vs dummy months

Demo seed writes May–July 2026 (`DEMO_CALENDAR_SEED_MONTHS`). Those months are
**not** the production merge gate.

Before snapshot/replay on Railway:

1. Confirm the first month with real production traffic (ops).
2. Classify only those live months.
3. Freeze the affected ID-only list as PR scope.

## Detect and freeze

From `backend/`:

```bash
python -m scripts.outgoing_calendar_day_clamp_audit --month 2026-08 --out ../exports
```

Audit columns (IDs only, no names): `case_id`, `case_code`, `therapist_user_id`,
`segment_start`, `segment_end`, `in_month_last_log`, `calendar_days`, `class`.

Classes: `out_of_month_end`, `pre_month_closed`, `control`, `unbounded_outgoing`.
Frozen scope = the first two.

### Frozen list (this checkout)

Local SQLite demo seed classify (2026-05 / 2026-06 / 2026-07 / 2026-08):
**zero outgoing Shadow/B2B calendar-day segments**, so the frozen list is empty.
Those May–July rows are dummy seed anyway and are not the merge gate.

Production Railway was not classified from this checkout (proxy closed). Ops
must run the audit against the first live traffic month and paste IDs here
before merge.

| Billing month | Live? | Frozen case_id × therapist_user_id | Class |
| --- | --- | --- | --- |
| 2026-05 | No (demo seed) | none | — |
| 2026-06 | No (demo seed) | none | — |
| 2026-07 | No (demo seed) | none | — |
| 2026-08 | Demo DB only (no seed traffic) | none | — |
| First live production month | TBD by ops | Run `python -m scripts.outgoing_calendar_day_clamp_audit --month YYYY-MM` on Railway | |

## Snapshot and bounded diff

`snapshot_calendar_day_money` writes payout segment rows + case client-gross.
Normalize: IDs and money only; sort by `case_id`, `therapist_user_id`,
`segment_start`. Drop timestamps and generated preview metadata.

Allowed to change (frozen rows only):

- `calendar_days`
- derived therapist payable
- derived client amount where it is computed from those Shadow/B2B days
- margin that follows those amounts

Must stay identical: `case_id`, `therapist_user_id`, raw `segment_start` /
`segment_end`, client rate / billing type, homecare session counts.

Every changed row must be in the frozen list. `diff_calendar_day_clamp_snapshots`
is the merge gate; tests-green is not sufficient for calendar-day money.

## After merge (not this patch)

### Locked-month arrears

If a live month was already paid or locked: `new − already paid = arrears`.
Pay the net delta in the next open month with pointers to the original run,
case IDs, reason, and commit SHA. Do not rewrite locked invoice truth.

### UI

Separate PR: blank calendar-days → explicit `0` plus a warning. Do not mix
that presentation change into the clamp.

### SS-188 data ticket

Separate **data** ticket for IC-2026-SS-188 (sessions recorded before
assignment start): case, sessions, recorded therapist, assignment start,
dates before start, actual provider, evidence, approved correction, finance
impact, owner. No assignment-date rewrite in the clamp.

## Out of scope

Package cycles, consume-on-submit, product control tower, leave
centralization, report v2 cutover.

# CM Evidence Review Dashboard (Pass 3 artifact)

_Status: artifact only — not implemented in Pass 1_

## Purpose

Case Managers review **exceptions**, not manual data entry. This dashboard surfaces evidence gaps before monthly report approval.

## Queue sections

| Queue | Source signal |
|-------|---------------|
| Weak evidence | `quality.evidence_strength == weak` |
| Unlinked goals | Goal entry without linked strategy |
| Missing child response | `child_response` null after V2 UI enabled |
| Custom strategies awaiting review | `is_custom_strategy == true` |
| Repeated distress signals | Multiple `child_agency_signal == distress_signal_observed` in month |
| Goals not addressed | IEP goals with zero materialized events in month |
| AI-suggested evidence pending | `field_provenance.* == ai_suggested` without human_selected override |

## API foundation (Pass 1)

Use rollup from:
`GET /api/v1/cases/{case_id}/clinical-evidence-events?month=YYYY-MM`

Pass 1 rollup already includes:
- `weak_evidence_count`
- `unlinked_goal_count`
- `custom_strategy_count`
- `gaps[]`

## UX

- Admin/CM portal, data-dense desktop
- Mobile-friendly exception cards ≤900px
- One-click navigate to session log for remediation

## Non-goals

- No auto-rejection of reports based on `evidence_strength` alone
- No punitive copy — connection before correction

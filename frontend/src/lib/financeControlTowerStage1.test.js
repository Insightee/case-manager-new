import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const overviewSrc = readFileSync(
  join(root, 'components/admin-portal/AdminFinanceOverviewTab.jsx'),
  'utf8',
)
const snapshotSrc = readFileSync(
  join(root, 'components/admin-portal/TherapistPayoutFinance.jsx'),
  'utf8',
)
const flagsSrc = readFileSync(join(root, 'lib/productFeatureFlags.js'), 'utf8')
const badgeSrc = readFileSync(
  join(root, 'components/admin-portal/ui/ConfidenceBadge.jsx'),
  'utf8',
)
const cssSrc = readFileSync(join(root, 'styles/finance-control-tower.css'), 'utf8')

describe('Finance Control Tower Stage 1 static contracts', () => {
  it('5 control tower UI only uses GET apiFetch paths (no mutating methods)', () => {
    const overviewCalls = [...overviewSrc.matchAll(/apiFetch\(([^)]*)\)/g)].map((m) => m[1])
    const snapshotCalls = [...snapshotSrc.matchAll(/apiFetch\(([^)]*)\)/g)].map((m) => m[1])
    assert.ok(overviewCalls.length >= 3)
    for (const call of overviewCalls) {
      assert.match(call, /finance-control-tower/)
      assert.doesNotMatch(call, /method:\s*['"]POST['"]/i)
    }
    const snapshotFinanceCalls = snapshotCalls.filter((call) =>
      /finance-control-tower/.test(call),
    )
    assert.ok(snapshotFinanceCalls.length >= 1)
    for (const call of snapshotFinanceCalls) {
      assert.doesNotMatch(call, /method:\s*['"]POST['"]/i)
    }
    assert.doesNotMatch(overviewSrc, /ensure-period-charges/)
    assert.doesNotMatch(overviewSrc, /method:\s*['"]POST['"]/)
  })

  it('9 finance summary lives in finance snapshot, not control tower tables', () => {
    assert.match(snapshotSrc, /financeSummary/)
    assert.match(snapshotSrc, /potentialBillable/)
    assert.match(snapshotSrc, /exceptionImpact/)
    assert.doesNotMatch(overviewSrc, /Action queue/)
    assert.doesNotMatch(overviewSrc, /Finance summary/)
  })

  it('11 ConfidenceBadge exposes text label + title tooltip', () => {
    assert.match(badgeSrc, /title=\{tip\}/)
    assert.match(badgeSrc, /aria-label=\{`Data confidence/)
    assert.match(badgeSrc, /Partial/)
    assert.match(badgeSrc, /Estimated/)
  })

  it('17 finance snapshot shows summary metric labels', () => {
    assert.match(snapshotSrc, /Potential billable/)
    assert.match(snapshotSrc, /Therapist payable/)
    assert.match(snapshotSrc, /finance-control-tower__summary-grid/)
    assert.doesNotMatch(snapshotSrc, /Money in · outstanding/)
    assert.doesNotMatch(snapshotSrc, /monday-brief/)
  })

  it('18 partial failure isolates section errors', () => {
    assert.match(overviewSrc, /Promise\.allSettled/)
    assert.match(overviewSrc, /financeOverviewErrorMessage/)
    assert.match(overviewSrc, /Billing readiness unavailable/)
    assert.match(snapshotSrc, /loadError/)
    assert.match(snapshotSrc, /Finance summary could not load/)
  })

  it('21 no authoritative profitability / contribution margin UI', () => {
    assert.doesNotMatch(overviewSrc, /contribution.?margin/i)
    assert.doesNotMatch(overviewSrc, /profitability/i)
    assert.doesNotMatch(overviewSrc, /gross margin/i)
    assert.doesNotMatch(snapshotSrc, /contribution.?margin/i)
  })

  it('24 no resolve / assign owner controls', () => {
    assert.doesNotMatch(overviewSrc, /Resolve exception/i)
    assert.doesNotMatch(overviewSrc, /Assign owner/i)
    assert.doesNotMatch(overviewSrc, /onResolve/)
    assert.match(overviewSrc, /Unassigned/)
  })

  it('feature flag VITE_ENABLE_FINANCE_DASHBOARD_V1 defaults on in non-prod with prod opt-in', () => {
    assert.match(flagsSrc, /VITE_ENABLE_FINANCE_DASHBOARD_V1/)
    assert.match(flagsSrc, /VITE_FINANCE_DASHBOARD_ALLOW_PROD/)
    assert.match(flagsSrc, /isFinanceDashboardV1Enabled/)
    assert.match(flagsSrc, /readFinanceDashboardV1Flag/)
    assert.match(flagsSrc, /rolloutDefault:\s*true/)
    assert.match(overviewSrc, /isFinanceDashboardV1Enabled/)
    assert.match(snapshotSrc, /isFinanceDashboardV1Enabled/)
    assert.match(overviewSrc, /Finance Control Tower opens when this environment is ready/)
    assert.match(snapshotSrc, /Finance snapshot is available in staging and preview/)
  })

  it('Forest Light scoped styles exist for control tower', () => {
    assert.match(cssSrc, /\.finance-control-tower/)
    assert.match(overviewSrc, /forest-light/)
    assert.match(overviewSrc, /finance-control-tower\.css/)
    assert.match(snapshotSrc, /finance-control-tower\.css/)
  })
})

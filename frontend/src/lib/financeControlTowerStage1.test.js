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
const flagsSrc = readFileSync(join(root, 'lib/productFeatureFlags.js'), 'utf8')
const badgeSrc = readFileSync(
  join(root, 'components/admin-portal/ui/ConfidenceBadge.jsx'),
  'utf8',
)
const cssSrc = readFileSync(join(root, 'styles/finance-control-tower.css'), 'utf8')

describe('Finance Control Tower Stage 1 static contracts', () => {
  it('5 control tower UI only uses GET apiFetch paths (no mutating methods)', () => {
    const calls = [...overviewSrc.matchAll(/apiFetch\(([^)]*)\)/g)].map((m) => m[1])
    assert.ok(calls.length >= 4)
    for (const call of calls) {
      assert.match(call, /finance-control-tower/)
      assert.doesNotMatch(call, /method:\s*['"]POST['"]/i)
      assert.doesNotMatch(call, /method:\s*['"]PUT['"]/i)
      assert.doesNotMatch(call, /method:\s*['"]PATCH['"]/i)
      assert.doesNotMatch(call, /method:\s*['"]DELETE['"]/i)
    }
    assert.doesNotMatch(overviewSrc, /ensure-period-charges/)
    assert.doesNotMatch(overviewSrc, /method:\s*['"]POST['"]/)
  })

  it('9 cards are driven from API actionQueue keys', () => {
    assert.match(overviewSrc, /summary\.actionQueue/)
    assert.match(overviewSrc, /readyForBilling/)
    assert.match(overviewSrc, /missingPackageCounts/)
    assert.match(overviewSrc, /openDisputes/)
  })

  it('11 ConfidenceBadge exposes text label + title tooltip', () => {
    assert.match(badgeSrc, /title=\{tip\}/)
    assert.match(badgeSrc, /aria-label=\{`Data confidence/)
    assert.match(badgeSrc, /Partial/)
    assert.match(badgeSrc, /Estimated/)
  })

  it('17 drill targets present (queue params + deep links)', () => {
    assert.match(overviewSrc, /next\.set\('queue'/)
    assert.match(overviewSrc, /Back to Control Tower/)
    assert.match(overviewSrc, /composerLedgerReady/)
    assert.match(overviewSrc, /links\.disputes/)
    assert.match(overviewSrc, /therapistPayouts/)
  })

  it('18 partial failure isolates section errors', () => {
    assert.match(overviewSrc, /Promise\.allSettled/)
    assert.match(overviewSrc, /Exception preview unavailable/)
    assert.match(overviewSrc, /Billing readiness unavailable/)
    assert.match(overviewSrc, /downgradeConfidence/)
  })

  it('21 no authoritative profitability / contribution margin UI', () => {
    assert.doesNotMatch(overviewSrc, /contribution.?margin/i)
    assert.doesNotMatch(overviewSrc, /profitability/i)
    assert.doesNotMatch(overviewSrc, /gross margin/i)
  })

  it('24 no resolve / assign owner controls', () => {
    assert.doesNotMatch(overviewSrc, /Resolve exception/i)
    assert.doesNotMatch(overviewSrc, /Assign owner/i)
    assert.doesNotMatch(overviewSrc, /onResolve/)
    assert.match(overviewSrc, /Unassigned/)
  })

  it('25 provisional banner when cutover incomplete', () => {
    assert.match(overviewSrc, /provisionalBanner/)
    assert.match(overviewSrc, /Live financial cutover is pending/)
    assert.match(overviewSrc, /figures remain\s+provisional/)
  })

  it('feature flag VITE_ENABLE_FINANCE_DASHBOARD_V1 defaults via readClientModuleFlag', () => {
    assert.match(flagsSrc, /VITE_ENABLE_FINANCE_DASHBOARD_V1/)
    assert.match(flagsSrc, /isFinanceDashboardV1Enabled/)
    assert.match(flagsSrc, /readClientModuleFlag\('VITE_ENABLE_FINANCE_DASHBOARD_V1'\)/)
    assert.match(overviewSrc, /isFinanceDashboardV1Enabled/)
    assert.match(overviewSrc, /Finance Control Tower is not enabled/)
  })

  it('Forest Light scoped styles exist for control tower', () => {
    assert.match(cssSrc, /\.finance-control-tower/)
    assert.match(overviewSrc, /forest-light/)
    assert.match(overviewSrc, /finance-control-tower\.css/)
  })
})

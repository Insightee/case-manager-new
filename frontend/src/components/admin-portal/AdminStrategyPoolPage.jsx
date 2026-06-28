import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { enrichStrategyPoolFromApi } from '../../lib/clinicalBrainMockData.js'
import { applyClinicalFilters, EMPTY_FILTERS, POOL_STATUS_TABS } from '../../lib/clinicalBrainFilters.js'
import { EVIDENCE_LABELS } from '../../lib/clinicalBrainCopy.js'
import { ClinicalBrainFilterOverlay } from '../clinical-brain/ClinicalBrainFilterOverlay.jsx'
import { ClinicalBrainStatusPill } from '../clinical-brain/ClinicalBrainStatusPill.jsx'
import { SubmitCustomStrategyForm } from '../clinical-brain/SubmitCustomStrategyForm.jsx'
import { canApproveOrgPool, canMergeBankItems } from '../../lib/clinicalBrainPermissions.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'
import { isClinicalBrainEnabled } from '../../lib/productFeatureFlags.js'
import '../../styles/clinical-brain.css'

export function AdminStrategyPoolPage() {
  if (!isClinicalBrainEnabled()) {
    return <PortalComingSoon variant="clinicalBrain" />
  }
  return <AdminStrategyPoolPageContent />
}

function AdminStrategyPoolPageContent() {
  const { user } = useAuth()
  const [tab, setTab] = useState('active')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [filterOpen, setFilterOpen] = useState(false)
  const [showDrawer, setShowDrawer] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/admin/strategy-pool')
      const strategies = res.items || []
      setItems(enrichStrategyPoolFromApi(strategies.length ? strategies : undefined))
    } catch (err) {
      setError(err.message || 'Could not load strategy pool')
      setItems(enrichStrategyPoolFromApi([]))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    const withTab = items.map((s) => ({
      ...s,
      _filter_status:
        s.status === 'approved' || s.status === 'active'
          ? 'active'
          : s.status === 'archived'
            ? 'deprecated'
            : s.is_pending
              ? 'needs_review'
              : 'candidates',
    }))
    return applyClinicalFilters(
      withTab.filter((s) => s._filter_status === tab || (tab === 'active' && s._filter_status === 'active')),
      filters,
    )
  }, [items, tab, filters])

  const canApprove = canApproveOrgPool(user)
  const canMerge = canMergeBankItems(user)

  return (
    <div className="gs-engine gs-engine-page cb-admin-pool">
      <header className="gs-engine-page__head">
        <div>
          <h1 className="gs-engine-page__title">Strategy Pool</h1>
          <p className="gs-engine-page__sub">Organisation-wide strategy supports and trials.</p>
        </div>
        <div className="gs-engine-actions">
          <button type="button" className="cb-btn" onClick={() => setFilterOpen(true)}>
            Filters
          </button>
          <button type="button" className="cb-btn cb-btn--primary" onClick={() => setShowDrawer(true)}>
            + New strategy
          </button>
        </div>
      </header>

      <div className="cb-strategy-picker__tabs">
        {POOL_STATUS_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`cb-strategy-picker__tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {msg ? <p className="gs-hint">{msg}</p> : null}
      {loading ? <p className="gs-muted">Loading strategy pool…</p> : null}
      {error ? <p className="gs-error">{error}</p> : null}

      <div className="cb-grid cb-grid--2">
        {filtered.map((s) => (
          <article key={s.id} className="cb-card">
            <div className="cb-card__head">
              <h3 className="cb-card__title">{s.label}</h3>
              <ClinicalBrainStatusPill
                status={s._filter_status === 'active' ? 'pool_active' : 'case_candidate'}
                kind="strategy"
              />
            </div>
            <p className="gs-muted">{s.purpose || s.when_to_use}</p>
            <div className="cb-card__meta">
              <span className="cb-pill cb-pill--active">{coreDomainLabel(s.domain_key, { short: true })}</span>
              {s.evidence_label ? (
                <span className="cb-pill cb-pill--progress">{EVIDENCE_LABELS[s.evidence_label]}</span>
              ) : null}
              <span>{s.usage_count ?? 0} uses</span>
            </div>
            {s.caution || s.avoid ? <p className="gs-muted text-sm">Caution: {s.caution || s.avoid}</p> : null}
            <div className="cb-card__actions">
              <button type="button" className="cb-btn">Edit</button>
              {canApprove ? (
                <button type="button" className="cb-btn cb-btn--primary" onClick={() => setMsg('Approve — TODO')}>
                  Approve
                </button>
              ) : null}
              {canMerge ? <button type="button" className="cb-btn">Merge</button> : null}
              <button type="button" className="cb-btn">Deprecate</button>
              <button type="button" className="cb-btn">View evidence</button>
            </div>
          </article>
        ))}
        {!loading && !filtered.length ? (
          <p className="gs-muted col-span-full">No strategies in this tab yet.</p>
        ) : null}
      </div>

      <ClinicalBrainFilterOverlay
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onApply={setFilters}
        showSupportLevel
        showEvidence
        showStatus
        statusOptions={POOL_STATUS_TABS}
      />

      {showDrawer ? (
        <SubmitCustomStrategyForm
          mode="admin"
          asDrawer
          onClose={() => setShowDrawer(false)}
          onSaved={() => {
            setShowDrawer(false)
            setMsg('Strategy saved.')
            load()
          }}
        />
      ) : null}
    </div>
  )
}

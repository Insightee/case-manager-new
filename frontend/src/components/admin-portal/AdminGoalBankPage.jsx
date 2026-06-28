import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { enrichGoalTemplatesFromApi } from '../../lib/clinicalBrainMockData.js'
import { applyClinicalFilters, BANK_STATUS_TABS, EMPTY_FILTERS } from '../../lib/clinicalBrainFilters.js'
import { ClinicalBrainFilterOverlay } from '../clinical-brain/ClinicalBrainFilterOverlay.jsx'
import { ClinicalBrainStatusPill } from '../clinical-brain/ClinicalBrainStatusPill.jsx'
import { canApproveOrgPool, canMergeBankItems } from '../../lib/clinicalBrainPermissions.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'
import { isClinicalBrainEnabled } from '../../lib/productFeatureFlags.js'
import '../../styles/clinical-brain.css'

export function AdminGoalBankPage() {
  if (!isClinicalBrainEnabled()) {
    return <PortalComingSoon variant="clinicalBrain" />
  }
  return <AdminGoalBankPageContent />
}

function AdminGoalBankPageContent() {
  const { user } = useAuth()
  const [tab, setTab] = useState('active')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [filterOpen, setFilterOpen] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/admin/goal-bank')
      const goals = res.items || []
      setItems(enrichGoalTemplatesFromApi(goals.length ? goals : undefined))
    } catch (err) {
      setError(err.message || 'Could not load goal bank')
      setItems(enrichGoalTemplatesFromApi([]))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    const withTab = items.map((g) => ({
      ...g,
      _filter_status:
        g.status === 'approved' || g.status === 'active'
          ? 'active'
          : g.status === 'archived'
            ? 'deprecated'
            : g.is_pending
              ? 'needs_review'
              : 'candidates',
    }))
    return applyClinicalFilters(
      withTab.filter((g) => tab === 'active' ? g._filter_status === 'active' : g._filter_status === tab || (tab === 'drafts' && g.status === 'local')),
      filters,
    )
  }, [items, tab, filters])

  const canApprove = canApproveOrgPool(user)
  const canMerge = canMergeBankItems(user)

  return (
    <div className="gs-engine gs-engine-page cb-admin-bank">
      <header className="gs-engine-page__head">
        <div>
          <h1 className="gs-engine-page__title">Goal Bank</h1>
          <p className="gs-engine-page__sub">Organisation-wide approved goal templates.</p>
        </div>
        <button type="button" className="cb-btn" onClick={() => setFilterOpen(true)}>
          Filters
        </button>
      </header>

      <div className="cb-strategy-picker__tabs">
        {BANK_STATUS_TABS.map((t) => (
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
      {loading ? <p className="gs-muted">Loading goal bank…</p> : null}
      {error ? <p className="gs-error">{error}</p> : null}

      <div className="cb-grid">
        {filtered.map((g) => (
          <article key={g.id} className="cb-card">
            <div className="cb-card__head">
              <h3 className="cb-card__title">{g.label}</h3>
              <ClinicalBrainStatusPill status={g._filter_status === 'active' ? 'approved_for_case' : 'case_candidate'} />
            </div>
            <div className="cb-card__meta">
              <span className="cb-pill cb-pill--active">{coreDomainLabel(g.domain_key, { short: true })}</span>
              {g.support_need ? <span>{g.support_need}</span> : null}
              <span>{g.related_strategies_count ?? 0} strategies</span>
              <span>{g.usage_count ?? 0} uses</span>
            </div>
            <p className="gs-muted">{g.goal_statement || g.parent_meaning}</p>
            <div className="cb-card__actions">
              <button type="button" className="cb-btn">Edit</button>
              {canApprove ? (
                <button type="button" className="cb-btn cb-btn--primary" onClick={() => setMsg('Approve — TODO: wire org approve endpoint')}>
                  Approve
                </button>
              ) : null}
              {canMerge ? (
                <button type="button" className="cb-btn" onClick={() => setMsg('Merge — TODO: wire merge endpoint')}>
                  Merge
                </button>
              ) : null}
              <button type="button" className="cb-btn">Deprecate</button>
            </div>
          </article>
        ))}
        {!loading && !filtered.length ? (
          <p className="gs-muted">No goals in this tab — adjust filters or add a draft.</p>
        ) : null}
      </div>

      <ClinicalBrainFilterOverlay
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onApply={setFilters}
        showStatus
        statusOptions={BANK_STATUS_TABS}
      />
    </div>
  )
}

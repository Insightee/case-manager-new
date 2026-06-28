import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { CLINICAL_QUALITY_DASHBOARD } from '../../lib/reportsRevampFlags.js'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'
import { isClinicalBrainEnabled } from '../../lib/productFeatureFlags.js'
import { ClinicalMetricCard } from '../clinical-ui/ClinicalMetricCard.jsx'
import { ClinicalCard } from '../clinical-ui/ClinicalCard.jsx'
import { ClinicalStatusBadge } from '../clinical-ui/ClinicalStatusBadge.jsx'
import '../../styles/case-profile-v2.css'

const RISK_COLOR = { high: 'var(--clinical-red)', medium: 'var(--clinical-amber)', low: 'var(--clinical-green)' }

export function AdminClinicalDashboardPage() {
  if (!isClinicalBrainEnabled()) {
    return <PortalComingSoon variant="clinicalBrain" />
  }
  return <AdminClinicalDashboardPageContent />
}

function AdminClinicalDashboardPageContent() {
  const [data, setData] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [dash, kpi] = await Promise.all([
        apiFetch('/api/v1/admin/clinical-dashboard'),
        apiFetch('/api/v1/admin/clinical-quality-dashboard/summary').catch(() => null),
      ])
      setData(dash)
      setSummary(kpi)
    } catch (err) {
      setError(err.message || 'Could not load clinical dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (!CLINICAL_QUALITY_DASHBOARD) {
    return (
      <div className="admin-page">
        <h1>Clinical dashboard</h1>
        <p className="admin-page__hint">Enable CLINICAL_QUALITY_DASHBOARD to use this view.</p>
      </div>
    )
  }

  if (loading) return <p className="admin-page__loading">Loading clinical dashboard…</p>
  if (error) return <p className="admin-page__error" style={{ color: 'var(--clinical-red)' }}>{error}</p>

  const totalCases     = summary?.total_cases     ?? data?.total_cases     ?? 0
  const urgentCount    = summary?.urgent_count    ?? data?.urgent_count    ?? 0
  const attentionCount = summary?.attention_count ?? data?.attention_count ?? 0
  const approvedCount  = summary?.approved_count  ?? data?.approved_count  ?? 0
  const pendingReview  = summary?.pending_review  ?? data?.pending_review  ?? 0
  const noLog7d        = summary?.no_log_7d       ?? data?.no_log_7d       ?? 0
  const candidates     = summary?.goal_candidates ?? data?.goal_candidates ?? 0
  const pendingIepChanges = summary?.pending_iep_changes ?? data?.pending_iep_changes ?? 0

  return (
    <div className="admin-page" style={{ background: 'var(--clinical-bg)', minHeight: '100vh', padding: '1.5rem' }}>
      <header className="clinical-page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="clinical-page-header__title">Clinical Quality Dashboard</h1>
        <p className="clinical-page-header__subtitle">
          Real-time documentation health across all active cases
        </p>
      </header>

      {/* 7 KPI metric cards */}
      <div className="clinical-metric-grid" style={{ marginBottom: '2rem' }}>
        <ClinicalMetricCard count={totalCases}     label="Active cases"       icon="🗂" />
        <ClinicalMetricCard count={urgentCount}    label="Urgent flags"       icon="🚨" accent="red" />
        <ClinicalMetricCard count={attentionCount} label="Need attention"     icon="⚠️" accent="amber" />
        <ClinicalMetricCard count={approvedCount}  label="Reports approved"   icon="✅" accent="green" />
        <ClinicalMetricCard count={pendingReview}  label="Pending CM review"  icon="👁" />
        <ClinicalMetricCard count={noLog7d}        label="No log (7 days)"    icon="📋" accent="amber" />
        <ClinicalMetricCard count={candidates}     label="Goal candidates"    icon="🎯" />
        <ClinicalMetricCard count={pendingIepChanges} label="Pending IEP changes" icon="📝" accent="amber" />
      </div>

      {/* Case grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
        {(data?.cases || []).length === 0 ? (
          <div className="clinical-empty-state" style={{ gridColumn: '1/-1' }}>
            <span className="clinical-empty-state__icon">🎉</span>
            <p className="clinical-empty-state__title">All cases are on track</p>
            <p className="clinical-empty-state__body">No clinical quality flags at this time.</p>
          </div>
        ) : (data?.cases || []).map((c) => (
          <ClinicalCard key={c.case_id}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <div>
                <p style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--clinical-text)', margin: 0 }}>
                  {c.child_name || c.case_code}
                </p>
                <p style={{ fontSize: '0.8125rem', color: 'var(--clinical-muted)', margin: '2px 0 0' }}>
                  {c.case_code}
                </p>
              </div>
              <span style={{
                fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                color: RISK_COLOR[c.risk_level] || 'var(--clinical-muted)',
                background: c.risk_level === 'high' ? 'var(--clinical-red-soft)' : c.risk_level === 'medium' ? 'var(--clinical-amber-soft)' : 'var(--clinical-green-soft)',
                padding: '2px 8px', borderRadius: 'var(--clinical-radius-pill)',
              }}>{c.risk_level}</span>
            </div>
            {c.documentation_status ? (
              <ClinicalStatusBadge status={c.documentation_status} style={{ marginBottom: '0.5rem' }} />
            ) : null}
            {c.missing_items?.length ? (
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.1rem', fontSize: '0.8125rem', color: 'var(--clinical-muted)' }}>
                {c.missing_items.slice(0, 3).map((m) => (
                  <li key={m}>{m.replace(/_/g, ' ')}</li>
                ))}
              </ul>
            ) : null}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
              <Link
                to={`/admin/cases/${c.case_id}`}
                style={{ fontSize: '0.8125rem', color: 'var(--clinical-purple)', fontWeight: 600, textDecoration: 'none' }}
              >
                Open Case →
              </Link>
              {c.pending_report_id ? (
                <Link
                  to={`/admin/reports/${c.pending_report_id}`}
                  style={{ fontSize: '0.8125rem', color: 'var(--clinical-amber)', fontWeight: 600, textDecoration: 'none' }}
                >
                  Review Report
                </Link>
              ) : null}
              {c.goal_candidate_id ? (
                <Link
                  to={`/admin/cases/${c.case_id}?tab=goals`}
                  style={{ fontSize: '0.8125rem', color: 'var(--clinical-green)', fontWeight: 600, textDecoration: 'none' }}
                >
                  Review Candidate
                </Link>
              ) : null}
              {c.pending_iep_changes > 0 ? (
                <Link
                  to={`/admin/cases/${c.case_id}?tab=reports&section=iep&view=builder`}
                  style={{ fontSize: '0.8125rem', color: 'var(--clinical-amber)', fontWeight: 600, textDecoration: 'none' }}
                >
                  IEP changes ({c.pending_iep_changes})
                </Link>
              ) : null}
            </div>
          </ClinicalCard>
        ))}
      </div>
    </div>
  )
}

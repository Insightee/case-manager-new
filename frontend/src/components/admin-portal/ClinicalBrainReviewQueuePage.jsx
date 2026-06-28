import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { REVIEW_QUEUE_TABS } from '../../lib/clinicalBrainFilters.js'
import { ClinicalBrainStatusPill } from '../clinical-brain/ClinicalBrainStatusPill.jsx'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'
import { isClinicalBrainEnabled } from '../../lib/productFeatureFlags.js'
import '../../styles/clinical-brain.css'

async function reviewItem(caseId, kind, itemId, action, note = '') {
  const path =
    kind === 'goal'
      ? `/api/v1/cases/${caseId}/goal-repository/${itemId}/review`
      : `/api/v1/cases/${caseId}/strategy-repository/${itemId}/review`
  return apiFetch(path, {
    method: 'POST',
    body: JSON.stringify({ action, note }),
  })
}

export function ClinicalBrainReviewQueuePage() {
  if (!isClinicalBrainEnabled()) {
    return <PortalComingSoon variant="clinicalBrain" />
  }
  return <ClinicalBrainReviewQueuePageContent />
}

function ClinicalBrainReviewQueuePageContent() {
  const [tab, setTab] = useState('goal_candidates')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')
  const [msg, setMsg] = useState('')
  const [returnNote, setReturnNote] = useState('')
  const [drawerItem, setDrawerItem] = useState(null)
  const [mergeOpen, setMergeOpen] = useState(false)
  const [mergeTargetId, setMergeTargetId] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [legacy, unified] = await Promise.all([
        apiFetch(`/api/v1/admin/clinical-review-queue?tab=${tab}`),
        apiFetch(`/api/v1/clinical-brain/review-queue?item_type=${tab === 'goal_candidates' ? 'custom_goal' : tab === 'strategy_candidates' ? 'custom_strategy' : ''}`).catch(() => ({ items: [] })),
      ])
      setData({ ...legacy, unified_items: unified.items || [] })
    } catch (err) {
      setError(err.message || 'Could not load review queue')
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    load()
  }, [load])

  async function unifiedAct(itemId, action, extra = {}) {
    setBusyId(`uq-${itemId}-${action}`)
    setMsg('')
    try {
      const note =
        action === 'request_revision' || action === 'reject'
          ? returnNote || 'Please add more detail.'
          : undefined
      await apiFetch(`/api/v1/clinical-brain/review-queue/${itemId}/action`, {
        method: 'POST',
        body: JSON.stringify({ action, reviewer_note: note, ...extra }),
      })
      setMsg(`Marked ${action.replace(/_/g, ' ')}.`)
      setReturnNote('')
      await load()
    } catch (err) {
      setMsg(err.message || 'Review action failed')
    } finally {
      setBusyId('')
    }
  }

  async function act(caseId, kind, itemId, action) {
    if (!caseId) return
    setBusyId(`${kind}-${itemId}-${action}`)
    setMsg('')
    try {
      const note = action === 'request_edits' ? returnNote || 'Please add more detail.' : ''
      await reviewItem(caseId, kind, itemId, action, note)
      setMsg(`Marked ${action.replace(/_/g, ' ')}.`)
      setReturnNote('')
      await load()
    } catch (err) {
      setMsg(err.message || 'Review action failed')
    } finally {
      setBusyId('')
    }
  }

  const goals = data?.pending_goals || []
  const strategies = data?.pending_strategies || []

  const items =
    tab === 'goal_candidates'
      ? goals.map((g) => ({ ...g, _kind: 'goal' }))
      : tab === 'strategy_candidates'
        ? strategies.map((s) => ({ ...s, _kind: 'strategy' }))
        : []

  return (
    <div className="gs-engine gs-engine-page cb-review-queue">
      <header className="gs-engine-page__head">
        <div>
          <h1 className="gs-engine-page__title">Clinical review queue</h1>
          <p className="gs-engine-page__sub">Review goal and strategy candidates for assigned cases.</p>
        </div>
      </header>

      <div className="cb-strategy-picker__tabs">
        {REVIEW_QUEUE_TABS.map((t) => (
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
      {loading ? <p className="gs-muted">Loading queue…</p> : null}
      {error ? <p className="gs-error">{error}</p> : null}

      {['missing_evidence', 'language_flags', 'reports', 'returned'].includes(tab) ? (
        <p className="gs-muted cb-insights-placeholder">
          {tab === 'missing_evidence' && 'Items missing linked evidence will appear here.'}
          {tab === 'language_flags' && 'Neuro-affirming language flags — TODO when backend endpoint is ready.'}
          {tab === 'reports' && 'Reports needing review use the existing reports workbench.'}
          {tab === 'returned' && 'Returned items awaiting therapist edits will appear here.'}
        </p>
      ) : (
        <div className="cb-grid">
          {items.map((item) => (
            <article key={`${item._kind}-${item.id}`} className="cb-card">
              <div className="cb-card__head">
                <h3 className="cb-card__title">{item.label}</h3>
                <ClinicalBrainStatusPill status="sent_for_review" kind={item._kind === 'strategy' ? 'strategy' : 'goal'} />
              </div>
              <div className="cb-card__meta">
                <span>{item.case_code ? `Case ${item.case_code}` : 'Case'}</span>
                {item.child_name ? <span>{item.child_name}</span> : null}
                <span>{item.created_by_name || 'Therapist'}</span>
                <span className="cb-pill cb-pill--active">
                  {coreDomainLabel((item.core_domains || [])[0] || item.domain_key, { short: true })}
                </span>
              </div>
              <p className="gs-muted">{item.goal_statement || item.when_to_use || item.rationale || '—'}</p>
              <section className="cb-insights-placeholder mt-2">
                <p className="m-0 text-sm font-semibold">Parent-safe preview</p>
                <p className="m-0 mt-1 text-sm">{item.parent_meaning || item.desired_state || 'Preview after approval.'}</p>
              </section>
              <label className="sg-field mt-2">
                <span className="sg-field__label">Return comment (optional)</span>
                <input value={returnNote} onChange={(e) => setReturnNote(e.target.value)} placeholder="What would help before approval?" />
              </label>
              <div className="cb-card__actions">
                <button
                  type="button"
                  className="cb-btn cb-btn--primary"
                  disabled={busyId === `${item._kind}-${item.id}-approve_case`}
                  onClick={() => act(item.case_id, item._kind, item.id, 'approve_case')}
                >
                  Approve for case
                </button>
                <button
                  type="button"
                  className="cb-btn"
                  disabled={busyId === `${item._kind}-${item.id}-request_edits`}
                  onClick={() => act(item.case_id, item._kind, item.id, 'request_edits')}
                >
                  Return with comment
                </button>
                <button
                  type="button"
                  className="cb-btn"
                  disabled={busyId === `${item._kind}-${item.id}-approve_pool`}
                  onClick={() => act(item.case_id, item._kind, item.id, 'approve_pool')}
                >
                  Send to {item._kind === 'goal' ? 'Goal Bank' : 'Strategy Pool'}
                </button>
                <button
                  type="button"
                  className="cb-btn"
                  disabled={busyId === `${item._kind}-${item.id}-reject`}
                  onClick={() => act(item.case_id, item._kind, item.id, 'reject')}
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
          {!loading && !items.length ? <p className="gs-muted">No candidates awaiting review.</p> : null}
        </div>
      )}

      {(data?.unified_items || []).length ? (
        <section className="mt-6">
          <h2 className="text-lg font-semibold">Unified queue</h2>
          <div className="cb-grid">
            {(data.unified_items || []).map((item) => (
              <article key={`uq-${item.id}`} className="cb-card">
                <div className="cb-card__head">
                  <h3 className="cb-card__title">{item.title || item.item_type}</h3>
                  <ClinicalBrainStatusPill status={item.status} kind="goal" />
                </div>
                <p className="gs-muted">{item.summary || '—'}</p>
                <div className="cb-card__actions">
                  <button type="button" className="cb-btn" onClick={() => setDrawerItem(item)}>
                    Details
                  </button>
                  <button type="button" className="cb-btn cb-btn--primary" onClick={() => unifiedAct(item.id, 'approve')}>
                    Approve
                  </button>
                  <button type="button" className="cb-btn" onClick={() => unifiedAct(item.id, 'request_revision')}>
                    Request revision
                  </button>
                  <button type="button" className="cb-btn" onClick={() => unifiedAct(item.id, 'mark_case_specific')}>
                    Case-specific
                  </button>
                  <button type="button" className="cb-btn" onClick={() => unifiedAct(item.id, 'close')}>
                    Close
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {drawerItem ? (
        <div className="cb-drawer" role="dialog" aria-modal="true" aria-label="Review item details">
          <button type="button" className="cb-drawer__backdrop" aria-label="Close" onClick={() => setDrawerItem(null)} />
          <div className="cb-drawer__panel">
            <header className="cb-drawer__head">
              <h2>{drawerItem.title || drawerItem.item_type}</h2>
              <button type="button" className="cb-filter-sheet__close" onClick={() => setDrawerItem(null)}>
                ×
              </button>
            </header>
            <p className="gs-muted">{drawerItem.summary || '—'}</p>
            {drawerItem.case_code ? <p>Case {drawerItem.case_code}</p> : null}
            {drawerItem.parent_safe_warning ? (
              <p className="gs-hint">{drawerItem.parent_safe_warning}</p>
            ) : (
              <p className="gs-hint">Parent-safe preview available after approval.</p>
            )}
            <label className="sg-field mt-2">
              <span className="sg-field__label">Reviewer note</span>
              <input value={returnNote} onChange={(e) => setReturnNote(e.target.value)} placeholder="Optional note for therapist or parent" />
            </label>
            <div className="cb-card__actions mt-4">
              <button type="button" className="cb-btn cb-btn--primary" onClick={() => unifiedAct(drawerItem.id, 'approve')}>
                Approve
              </button>
              <button
                type="button"
                className="cb-btn"
                onClick={() => {
                  setMergeOpen(true)
                }}
              >
                Merge to library
              </button>
              <button type="button" className="cb-btn" onClick={() => unifiedAct(drawerItem.id, 'close')}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {mergeOpen && drawerItem ? (
        <div className="cb-drawer" role="dialog" aria-modal="true" aria-label="Merge to library">
          <button type="button" className="cb-drawer__backdrop" aria-label="Close" onClick={() => setMergeOpen(false)} />
          <div className="cb-drawer__panel">
            <h2>Merge to library</h2>
            <p className="gs-muted">Link this item to an existing Goal Bank or Strategy Pool entry.</p>
            <label className="sg-field">
              <span className="sg-field__label">Library item ID</span>
              <input value={mergeTargetId} onChange={(e) => setMergeTargetId(e.target.value)} placeholder="e.g. 12" />
            </label>
            <div className="cb-card__actions mt-4">
              <button
                type="button"
                className="cb-btn cb-btn--primary"
                onClick={async () => {
                  if (!mergeTargetId.trim()) return
                  await unifiedAct(drawerItem.id, 'merge', {
                    linked_library_goal_id: drawerItem.item_type === 'custom_goal' ? Number(mergeTargetId) : undefined,
                    linked_library_strategy_id: drawerItem.item_type === 'custom_strategy' ? Number(mergeTargetId) : undefined,
                  })
                  setMergeOpen(false)
                  setDrawerItem(null)
                  setMergeTargetId('')
                }}
              >
                Confirm merge
              </button>
              <button type="button" className="cb-btn" onClick={() => setMergeOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

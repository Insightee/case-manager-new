import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { CreateStrategyModal } from '../../clinical/goals-strategy/CreateStrategyModal.jsx'

export function IepStrategyLinker({ caseId, reportId, goal, open, onClose, onLinked }) {
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !caseId) return
    apiFetch(`/api/v1/cases/${caseId}/reports/iep/available-strategies?goal_id=${goal?.iep_goal_id || ''}`)
      .then((data) => setItems(data.items || []))
      .catch(() => setItems([]))
  }, [open, caseId, goal?.iep_goal_id])

  const filtered = items.filter((s) => !q || (s.label || '').toLowerCase().includes(q.toLowerCase()))

  async function link(strategyId) {
    if (!reportId || !goal?.iep_goal_id) return
    setBusy(true)
    try {
      await apiFetch(`/api/v1/reports/${reportId}/iep/goals/${goal.iep_goal_id}/strategies`, {
        method: 'POST',
        body: JSON.stringify({ strategy_id: strategyId, strategy_source_type: 'repository' }),
      })
      onLinked?.()
      onClose?.()
    } finally {
      setBusy(false)
    }
  }

  if (!open) return null

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 p-4">
        <div className="bg-surface-container-lowest w-full max-w-lg rounded-xl clinical-shadow p-6 max-h-[85vh] overflow-y-auto">
          <h2 className="text-lg font-bold m-0 mb-2">Link strategy</h2>
          <p className="text-sm text-on-surface-variant m-0 mb-4">For: {goal?.title || goal?.goal_statement}</p>
          <input
            className="w-full min-h-[44px] rounded-xl border border-outline-variant/50 px-3 mb-3"
            placeholder="Search strategies…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ul className="space-y-2 mb-4">
            {filtered.map((s) => (
              <li key={s.id} className="flex justify-between items-center gap-2 border border-outline-variant/30 rounded-lg p-3">
                <span className="text-sm font-medium">{s.label}</span>
                <button
                  type="button"
                  disabled={busy}
                  className="min-h-[44px] px-3 rounded-lg bg-lush-forest text-white text-sm font-bold"
                  onClick={() => link(s.id)}
                >
                  Link
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="w-full min-h-[44px] rounded-xl border font-semibold" onClick={() => setShowCreate(true)}>
            Create strategy candidate
          </button>
          <button type="button" className="w-full min-h-[44px] mt-2 rounded-xl text-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
      {showCreate ? (
        <CreateStrategyModal
          caseId={caseId}
          clinicalReportId={reportId}
          iepGoalId={goal?.iep_goal_id}
          goalLabel={goal?.title || goal?.goal_statement}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            onLinked?.()
            onClose?.()
          }}
        />
      ) : null}
    </>
  )
}

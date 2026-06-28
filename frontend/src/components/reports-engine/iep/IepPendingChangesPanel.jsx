import { useState } from 'react'

function PendingChangeRow({ change, readOnly, onApprove, onReturn }) {
  const [returnOpen, setReturnOpen] = useState(false)
  const [comment, setComment] = useState('')

  return (
    <li className="bg-white rounded-lg p-3 border border-outline-variant/30">
      <p className="text-sm font-semibold m-0 capitalize">{change.change_type?.replace(/_/g, ' ')}</p>
      <p className="text-xs text-on-surface-variant m-0 mt-1">{change.iep_goal_id}</p>
      {!readOnly ? (
        <div className="mt-3 space-y-2">
          {returnOpen ? (
            <div className="space-y-2">
              <label className="block text-xs font-bold text-outline">
                Note for therapist
                <textarea
                  className="mt-1 w-full min-h-[72px] rounded-lg border border-outline-variant/50 p-2 text-sm"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="What should they adjust before resubmitting?"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="min-h-[44px] px-3 rounded-lg bg-lush-forest text-white text-sm font-bold"
                  disabled={!comment.trim()}
                  onClick={() => {
                    onReturn?.([change.change_id], comment.trim())
                    setReturnOpen(false)
                    setComment('')
                  }}
                >
                  Send return note
                </button>
                <button
                  type="button"
                  className="min-h-[44px] px-3 rounded-lg border text-sm"
                  onClick={() => {
                    setReturnOpen(false)
                    setComment('')
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                className="min-h-[44px] px-3 rounded-lg bg-lush-forest text-white text-sm font-bold"
                onClick={() => onApprove?.([change.change_id])}
              >
                Approve
              </button>
              <button
                type="button"
                className="min-h-[44px] px-3 rounded-lg border text-sm"
                onClick={() => setReturnOpen(true)}
              >
                Return
              </button>
            </div>
          )}
        </div>
      ) : null}
    </li>
  )
}

export function IepPendingChangesPanel({ items, onApprove, onReturn, readOnly }) {
  if (!items?.length) return null
  return (
    <section className="rounded-xl border border-amber-300 bg-amber-50 p-4 mb-6">
      <h3 className="text-sm font-bold m-0 mb-3">Pending changes ({items.length})</h3>
      <ul className="space-y-3">
        {items.map((c) => (
          <PendingChangeRow
            key={c.change_id}
            change={c}
            readOnly={readOnly}
            onApprove={onApprove}
            onReturn={onReturn}
          />
        ))}
      </ul>
    </section>
  )
}

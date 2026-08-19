import { useState } from 'react'
import { formatDisplayDate } from '../../../lib/datetime.js'

const STATUS_LABEL = {
  pending: 'Awaiting response',
  approved: 'Approved',
  auto_approved: 'Auto-approved',
  review_requested: 'Review requested',
}

export function IepApprovalPanel({
  approval = {},
  reviewThread = [],
  variant = 'therapist',
  readOnly = false,
  onSendForStakeholderApproval,
  onStakeholderApprove,
  onStakeholderRequestReview,
  onCmResend,
  busy = false,
}) {
  const [comment, setComment] = useState('')
  const [cmReply, setCmReply] = useState('')

  if (!approval?.phase) return null

  const isCm = variant === 'admin'
  const isParent = variant === 'parent'
  const role = isParent ? 'parent' : 'therapist'

  return (
    <section className="cr-section mb-6 border-l-4 border-lush-forest pl-4">
      <p className="cr-section__label m-0 mb-2">Approval & review</p>
      <div className="grid sm:grid-cols-2 gap-3 text-sm mb-4">
        <div className="rounded-lg border p-3 bg-surface-container-low">
          <p className="text-xs uppercase text-outline m-0">Therapist</p>
          <p className="font-semibold m-0">{STATUS_LABEL[approval.therapist_approval_status] || '—'}</p>
        </div>
        <div className="rounded-lg border p-3 bg-surface-container-low">
          <p className="text-xs uppercase text-outline m-0">Parent / family</p>
          <p className="font-semibold m-0">{STATUS_LABEL[approval.parent_approval_status] || '—'}</p>
        </div>
      </div>

      {reviewThread.length > 0 ? (
        <div className="mb-4 max-h-48 overflow-y-auto space-y-2">
          {reviewThread.map((item) => (
            <div key={item.id} className="text-sm p-2 rounded-lg bg-white border border-outline-variant/20">
              <p className="text-xs text-on-surface-variant m-0 mb-1">
                {item.actor_role || 'Team'} · {item.event_type?.replace(/_/g, ' ')}
                {item.created_at ? ` · ${formatDisplayDate(item.created_at.slice(0, 10))}` : ''}
              </p>
              {item.comment ? <p className="m-0">{item.comment}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {isCm && !approval.review_active && approval.phase === 'stakeholder' && !readOnly ? (
        <button type="button" className="cr-btn cr-btn--forest mb-3" disabled={busy} onClick={onSendForStakeholderApproval}>
          Send to parent & therapist for approval
        </button>
      ) : null}

      {isCm && approval.review_active && !readOnly ? (
        <div className="mb-3">
          <textarea
            className="w-full rounded-xl border p-3 text-sm mb-2 min-h-[72px]"
            placeholder="Reply to review request and note what changed…"
            value={cmReply}
            onChange={(e) => setCmReply(e.target.value)}
          />
          <button type="button" className="cr-btn cr-btn--primary" disabled={busy || cmReply.trim().length < 5} onClick={() => onCmResend?.(cmReply)}>
            Resend for approval
          </button>
        </div>
      ) : null}

      {!isCm && approval.phase === 'stakeholder' && !approval.review_active && !readOnly ? (
        <div className="flex flex-col gap-2">
          <textarea
            className="w-full rounded-xl border p-3 text-sm min-h-[72px]"
            placeholder="Optional note if requesting review…"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button type="button" className="cr-btn cr-btn--forest" disabled={busy} onClick={() => onStakeholderApprove?.(role)}>
              Approve plan
            </button>
            <button
              type="button"
              className="cr-btn"
              disabled={busy || comment.trim().length < 5}
              onClick={() => onStakeholderRequestReview?.(role, comment)}
            >
              Request review
            </button>
          </div>
          <p className="text-xs text-on-surface-variant m-0">If no response in 10 days, your side auto-approves unless you request review.</p>
        </div>
      ) : null}
    </section>
  )
}

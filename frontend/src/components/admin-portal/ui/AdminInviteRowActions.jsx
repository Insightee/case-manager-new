import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { inviteEmailMessage } from '../../../lib/inviteEmail.js'
import { CopyLinkButton } from './CopyLinkButton.jsx'

export function AdminInviteRowActions({
  invite,
  onSuccess,
  onError,
  onReload,
  showResend = true,
}) {
  const [resending, setResending] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [actionMessage, setActionMessage] = useState('')

  async function resend() {
    if (!invite?.id) return
    onError?.('')
    setResending(true)
    try {
      const res = await apiFetch(`/api/v1/admin/invites/${invite.id}/resend-email`, { method: 'POST' })
      const msg = inviteEmailMessage(invite.email, res.email_delivery)
      if (res.email_delivery === 'skipped_no_smtp') {
        onError?.(msg)
        setActionMessage('Resend failed — email not configured')
      } else {
        onSuccess?.(msg)
        setActionMessage('Invite email sent again')
      }
    } catch (err) {
      onError?.(err.message || 'Could not resend invite email')
      setActionMessage('Resend failed')
    } finally {
      setResending(false)
    }
  }

  async function cancel() {
    if (!invite?.id) return
    if (!window.confirm(`Cancel invite for ${invite.email}? The link will stop working.`)) return
    onError?.('')
    setCancelling(true)
    try {
      await apiFetch(`/api/v1/admin/invites/${invite.id}/revoke`, { method: 'POST' })
      onSuccess?.(`Invite cancelled for ${invite.email}.`)
      setActionMessage('Invite cancelled')
      onReload?.()
    } catch (err) {
      onError?.(err.message || 'Could not cancel invite')
      setActionMessage('Cancel failed')
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="admin-btn-group" role="group" aria-label={`Invite actions for ${invite?.email || 'user'}`}>
      <p className="admin-muted" style={{ flexBasis: '100%', margin: '0 0 4px', fontSize: '0.75rem' }}>
        Cancel only affects unused links. After someone registers, use Deactivate or Invite to login on their row.
      </p>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {actionMessage}
      </span>
      <CopyLinkButton url={invite?.invite_url} />
      {showResend ? (
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={resending || cancelling}
          onClick={resend}
          aria-busy={resending}
          style={{ minHeight: 44 }}
        >
          {resending ? 'Sending…' : 'Resend email'}
        </button>
      ) : null}
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        disabled={resending || cancelling}
        onClick={cancel}
        aria-busy={cancelling}
        aria-label={`Cancel invite for ${invite?.email || 'user'}`}
        style={{ minHeight: 44, minWidth: 44 }}
      >
        {cancelling ? 'Cancelling…' : 'Cancel'}
      </button>
    </div>
  )
}

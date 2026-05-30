import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPageHeader } from './ui/index.js'
import { InvoiceLineItemEditor } from './InvoiceLineItemEditor.jsx'
import { ClientInvoiceOverviewPanel } from './ClientInvoiceOverviewPanel.jsx'
import { formatCurrency } from './ui/index.js'
import './admin-client-invoices.css'
import './admin-client-invoices-composer.css'

export function AdminClientInvoicePage() {
  const { invoiceId } = useParams()
  const { canWriteBilling } = useModuleWrite()
  const id = Number(invoiceId)
  const [detail, setDetail] = useState(null)
  const [tab, setTab] = useState('overview')
  const [audit, setAudit] = useState([])
  const [paymentPolicy, setPaymentPolicy] = useState('')
  const [gatewayEnabled, setGatewayEnabled] = useState(false)
  const [acting, setActing] = useState(false)

  const load = useCallback(() => {
    if (!id) return
    apiFetch(`/api/v1/admin/client-billing/invoices/${id}`)
      .then((d) => {
        setDetail(d)
        setPaymentPolicy(d.paymentPolicySnapshot || '')
        setGatewayEnabled(Boolean(d.gatewayEnabled))
      })
      .catch(() => setDetail(null))
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!id || tab !== 'audit') return
    apiFetch(`/api/v1/admin/client-billing/invoices/${id}/audit-trail`)
      .then((r) => setAudit(r.items || []))
      .catch(() => setAudit([]))
  }, [id, tab])

  async function sendToClient() {
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${id}/notify-parent?resend=true`, { method: 'POST' })
      load()
    } finally {
      setActing(false)
    }
  }

  async function markGenerated() {
    await apiFetch(`/api/v1/admin/client-billing/invoices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'GENERATED' }),
    })
    load()
  }

  async function saveMeta() {
    await apiFetch(`/api/v1/admin/client-billing/invoices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        payment_policy_snapshot: paymentPolicy,
        gateway_enabled: gatewayEnabled,
      }),
    })
    load()
  }

  if (!id) {
    return (
      <div className="admin-page">
        <p>Invalid invoice.</p>
        <Link to="/admin/invoices?tab=client">Back to client invoices</Link>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="admin-page">
        <div className="admin-skeleton" />
      </div>
    )
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title={detail.invoiceNumber}
        subtitle={`${detail.childName} · ${detail.caseId} · Full invoice view`}
      />
      <p style={{ marginBottom: 16 }}>
        <Link to="/admin/invoices?tab=client">← All client invoices</Link>
        {' · '}
        <Link to={`/admin/invoices/compose?case_id=${detail.caseDbId}&billing_month=${encodeURIComponent(detail.billingMonth || '')}`}>
          Open in composer
        </Link>
      </p>

      <div className="client-inv__drawer-tabs">
        {['overview', 'lines', 'payments', 'policy', 'audit'].map((t) => (
          <button
            key={t}
            type="button"
            className={`client-inv__drawer-tab ${tab === t ? 'is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <ClientInvoiceOverviewPanel
          detail={detail}
          canWriteBilling={canWriteBilling}
          acting={acting}
          onSendToClient={sendToClient}
          onMarkGenerated={markGenerated}
        />
      ) : null}

      {tab === 'lines' ? (
        <InvoiceLineItemEditor
          invoiceId={id}
          lines={detail.lines || []}
          detail={detail}
          canWrite={canWriteBilling && detail.status === 'DRAFT'}
          onUpdated={load}
        />
      ) : null}

      {tab === 'payments' ? (
        <div style={{ marginTop: 16 }}>
          {(detail.payments || []).length === 0 ? (
            <p style={{ color: '#94a3b8' }}>No payments recorded.</p>
          ) : (
            detail.payments.map((p) => (
              <div key={p.id} style={{ padding: '10px 0', borderBottom: '1px solid #e2e8f0' }}>
                {formatCurrency(p.amountInr)} · {p.method} · {(p.paymentStatus || '').replaceAll('_', ' ')}
              </div>
            ))
          )}
          {(detail.disputes || []).length > 0 ? (
            <>
              <h4 style={{ marginTop: 20 }}>Disputes</h4>
              {detail.disputes.map((d) => (
                <div key={d.id} style={{ fontSize: '0.85rem', marginBottom: 8 }}>
                  {d.reasonCode}: {d.message}
                </div>
              ))}
            </>
          ) : null}
        </div>
      ) : null}

      {tab === 'policy' && canWriteBilling ? (
        <div style={{ marginTop: 16, maxWidth: 640 }}>
          <label style={{ display: 'block', marginBottom: 12 }}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Payment policy (snapshot on send)</span>
            <textarea
              className="client-inv__filter-input"
              style={{ width: '100%', minHeight: 160, marginTop: 6 }}
              value={paymentPolicy}
              onChange={(e) => setPaymentPolicy(e.target.value)}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <input type="checkbox" checked={gatewayEnabled} onChange={(e) => setGatewayEnabled(e.target.checked)} />
            Enable payment gateway link
          </label>
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={saveMeta}>
            Save policy & gateway
          </button>
        </div>
      ) : null}

      {tab === 'audit' ? (
        <ul style={{ marginTop: 16, paddingLeft: 20, fontSize: '0.85rem' }}>
          {audit.length === 0 ? <li>No audit events</li> : null}
          {audit.map((ev) => (
            <li key={ev.id} style={{ marginBottom: 8 }}>
              <strong>{ev.actor_name}</strong> {ev.action} {ev.entity_type} · {ev.created_at?.slice(0, 10)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

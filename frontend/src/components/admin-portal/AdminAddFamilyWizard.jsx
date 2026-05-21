import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AddressFormFields, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'

const MODULES = [
  { id: 'homecare', label: 'Homecare' },
  { id: 'shadow_support', label: 'Shadow support' },
]

const SERVICE_PRESETS = {
  homecare: ['Homecare', 'Occupational therapy', 'Speech therapy', 'Physiotherapy'],
  shadow_support: ['Shadow support', 'School inclusion', 'Community support'],
}

const EMPTY_BILLING = {
  billing_type: 'PER_SESSION',
  client_billing_mode: 'POSTPAID',
  client_rate_per_session_inr: '1000',
  pay_share_pct: '60',
  package_session_count: '12',
  package_amount_inr: '12000',
  compensation_mode: 'PERCENTAGE',
  therapist_fixed_pay_inr: '',
}

const EMPTY_CHILD = { first_name: '', last_name: '', date_of_birth: '' }
const EMPTY_PARENT = { email: '', full_name: '', phone: '', send_invite: true }

export function AdminAddFamilyWizard({ onComplete, onCancel }) {
  const [mode, setMode] = useState('new')
  const [step, setStep] = useState(1)
  const [createCase, setCreateCase] = useState(false)
  const [child, setChild] = useState(EMPTY_CHILD)
  const [parent, setParent] = useState(EMPTY_PARENT)
  const [linkChildId, setLinkChildId] = useState('')
  const [linkEmail, setLinkEmail] = useState('')
  const [orphanChildren, setOrphanChildren] = useState([])
  const [productModule, setProductModule] = useState('homecare')
  const [caseCode, setCaseCode] = useState('')
  const [serviceType, setServiceType] = useState('Homecare')
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [billing, setBilling] = useState(EMPTY_BILLING)
  const [therapistId, setTherapistId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')

  const loadOrphans = useCallback(() => {
    apiFetch('/api/v1/admin/families')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : []
        setOrphanChildren(list.filter((f) => !f.hasParent && !f.pendingInvite))
      })
      .catch(() => setOrphanChildren([]))
  }, [])

  useEffect(() => {
    if (mode === 'link') loadOrphans()
  }, [mode, loadOrphans])

  useEffect(() => {
    if (!createCase || step < 2) return
    apiFetch(`/api/v1/admin/cases/next-code?product_module=${encodeURIComponent(productModule)}`)
      .then((r) => setCaseCode(r.case_code))
      .catch(() => setCaseCode(''))
  }, [productModule, createCase, step])

  useEffect(() => {
    const presets = SERVICE_PRESETS[productModule] || []
    if (presets.length) setServiceType(presets[0])
  }, [productModule])

  function setBill(key, value) {
    setBilling((b) => {
      const next = { ...b, [key]: value }
      if (key === 'billing_type') {
        next.client_billing_mode = value === 'PACKAGE' ? 'PREPAID' : 'POSTPAID'
      }
      return next
    })
  }

  const totalSteps = mode === 'link' ? 1 : createCase ? 4 : 1

  async function submitFamily() {
    const fam = await apiFetch('/api/v1/admin/families', {
      method: 'POST',
      body: JSON.stringify({
        parent_email: parent.email.trim(),
        parent_full_name: parent.full_name.trim(),
        parent_phone: parent.phone.trim() || null,
        child: {
          first_name: child.first_name.trim(),
          last_name: child.last_name.trim(),
          date_of_birth: child.date_of_birth || null,
        },
        send_invite: parent.send_invite,
      }),
    })
    if (fam.inviteUrl) setInviteUrl(fam.inviteUrl)
    return fam.childId
  }

  async function submitLink() {
    await apiFetch(
      `/api/v1/admin/families/link-by-email?child_id=${encodeURIComponent(linkChildId)}&parent_email=${encodeURIComponent(linkEmail.trim())}`,
      { method: 'POST' },
    )
    onComplete?.({ mode: 'link' })
  }

  async function submitAllot(childId) {
    const payload = {
      child_id: childId,
      service_type: serviceType.trim(),
      product_module: productModule,
      case_code: caseCode || undefined,
      billing_type: billing.billing_type,
      client_billing_mode: billing.client_billing_mode,
      compensation_mode: billing.compensation_mode,
      pay_share_pct: Number(billing.pay_share_pct),
      therapist_user_id: Number(therapistId),
    }
    if (billing.billing_type === 'PER_SESSION') {
      payload.client_rate_per_session_inr = Number(billing.client_rate_per_session_inr)
    } else {
      payload.package_session_count = Number(billing.package_session_count)
      payload.package_amount_inr = Number(billing.package_amount_inr)
    }
    if (productModule === 'homecare' && serviceAddr.address_line1) {
      const base = addressToPayload(serviceAddr)
      Object.assign(payload, {
        service_address_line1: base.address_line1,
        service_address_line2: base.address_line2,
        service_city: base.city,
        service_state: base.state,
        service_pincode: base.pincode,
        service_landmark: base.landmark,
      })
    }
    return apiFetch('/api/v1/admin/cases/allot', { method: 'POST', body: JSON.stringify(payload) })
  }

  async function handleFinish() {
    setSaving(true)
    setError('')
    try {
      if (mode === 'link') {
        if (!linkChildId || !linkEmail.trim()) throw new Error('Select child and parent email')
        await submitLink()
        return
      }
      if (!child.first_name.trim() || !child.last_name.trim()) throw new Error('Child name required')
      if (!parent.email.trim() || !parent.full_name.trim()) throw new Error('Parent name and email required')

      const childId = await submitFamily()
      if (createCase) {
        if (!therapistId) throw new Error('Select a therapist')
        const result = await submitAllot(childId)
        onComplete?.({ childId, case: result.case, inviteUrl })
      } else {
        onComplete?.({ childId, inviteUrl })
      }
    } catch (err) {
      setError(err.message || 'Could not save family')
    } finally {
      setSaving(false)
    }
  }

  function handleNext() {
    if (mode === 'link') {
      handleFinish()
      return
    }
    if (step === 1 && !createCase) {
      handleFinish()
      return
    }
    if (step < totalSteps) setStep((s) => s + 1)
    else handleFinish()
  }

  return (
    <section className="admin-panel" style={{ marginBottom: 20, padding: 16, border: '1px solid #e2e8f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <p className="admin-drawer__subtitle">Add family</p>
          <p className="admin-muted" style={{ fontSize: '0.85rem', margin: 0 }}>
            {mode === 'link'
              ? 'Link an existing child to a parent account by email'
              : `Step ${step} of ${totalSteps}`}
          </p>
        </div>
        {onCancel ? (
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onCancel}>
            Close
          </button>
        ) : null}
      </div>

      <div className="admin-btn-group" style={{ marginBottom: 16 }}>
        {[
          { id: 'new', label: 'New family' },
          { id: 'link', label: 'Link existing' },
        ].map((m) => (
          <button
            key={m.id}
            type="button"
            className={`admin-btn admin-btn--sm ${mode === m.id ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => {
              setMode(m.id)
              setStep(1)
              setError('')
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {inviteUrl ? (
        <p className="admin-alert admin-alert--success" style={{ wordBreak: 'break-all', fontSize: '0.85rem' }}>
          Parent invite link: {inviteUrl}
        </p>
      ) : null}

      {mode === 'link' ? (
        <div className="admin-form-grid" style={{ maxWidth: 480 }}>
          <label style={{ gridColumn: '1 / -1' }}>
            Child without parent
            <select className="admin-input" value={linkChildId} onChange={(e) => setLinkChildId(e.target.value)}>
              <option value="">Select…</option>
              {orphanChildren.map((f) => (
                <option key={f.childId} value={f.childId}>
                  {f.childName} (#{f.childId})
                </option>
              ))}
            </select>
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Parent email (existing account)
            <input
              type="email"
              className="admin-input"
              value={linkEmail}
              onChange={(e) => setLinkEmail(e.target.value)}
              placeholder="parent@example.com"
            />
          </label>
        </div>
      ) : null}

      {mode === 'new' && step === 1 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Child first name
            <input
              className="admin-input"
              value={child.first_name}
              onChange={(e) => setChild((c) => ({ ...c, first_name: e.target.value }))}
              required
            />
          </label>
          <label>
            Child last name
            <input
              className="admin-input"
              value={child.last_name}
              onChange={(e) => setChild((c) => ({ ...c, last_name: e.target.value }))}
              required
            />
          </label>
          <label>
            Date of birth (optional)
            <input
              type="date"
              className="admin-input"
              value={child.date_of_birth}
              onChange={(e) => setChild((c) => ({ ...c, date_of_birth: e.target.value }))}
            />
          </label>
          <label>
            Parent name
            <input
              className="admin-input"
              value={parent.full_name}
              onChange={(e) => setParent((p) => ({ ...p, full_name: e.target.value }))}
            />
          </label>
          <label>
            Parent email
            <input
              type="email"
              className="admin-input"
              value={parent.email}
              onChange={(e) => setParent((p) => ({ ...p, email: e.target.value }))}
            />
          </label>
          <label>
            Parent phone
            <input
              className="admin-input"
              value={parent.phone}
              onChange={(e) => setParent((p) => ({ ...p, phone: e.target.value }))}
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <input
              type="checkbox"
              checked={parent.send_invite}
              onChange={(e) => setParent((p) => ({ ...p, send_invite: e.target.checked }))}
            />{' '}
            Send portal invite email
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <input
              type="checkbox"
              checked={createCase}
              onChange={(e) => {
                setCreateCase(e.target.checked)
                setStep(1)
              }}
            />{' '}
            Create case and assign therapist now
          </label>
        </div>
      ) : null}

      {mode === 'new' && createCase && step === 2 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Module
            <select className="admin-input" value={productModule} onChange={(e) => setProductModule(e.target.value)}>
              {MODULES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Case code
            <input className="admin-input" value={caseCode} readOnly />
          </label>
          <label>
            Service type
            <input
              className="admin-input"
              list="add-family-service-presets"
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
            />
            <datalist id="add-family-service-presets">
              {(SERVICE_PRESETS[productModule] || []).map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </label>
          {productModule === 'homecare' ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <p className="admin-drawer__subtitle">Service address (optional)</p>
              <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="fam-svc" showLocationButton={false} />
            </div>
          ) : null}
        </div>
      ) : null}

      {mode === 'new' && createCase && step === 3 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Client billing
            <select
              className="admin-input"
              value={billing.client_billing_mode}
              onChange={(e) => setBill('client_billing_mode', e.target.value)}
            >
              <option value="POSTPAID">Postpaid</option>
              <option value="PREPAID">Prepaid</option>
            </select>
          </label>
          <label>
            Therapist billing
            <select className="admin-input" value={billing.billing_type} onChange={(e) => setBill('billing_type', e.target.value)}>
              <option value="PER_SESSION">Per session</option>
              <option value="PACKAGE">Package</option>
            </select>
          </label>
          {billing.billing_type === 'PER_SESSION' ? (
            <>
              <label>
                Rate / session (INR)
                <input
                  type="number"
                  className="admin-input"
                  value={billing.client_rate_per_session_inr}
                  onChange={(e) => setBill('client_rate_per_session_inr', e.target.value)}
                />
              </label>
              <label>
                Therapist share %
                <input
                  type="number"
                  className="admin-input"
                  value={billing.pay_share_pct}
                  onChange={(e) => setBill('pay_share_pct', e.target.value)}
                />
              </label>
            </>
          ) : (
            <>
              <label>
                Package sessions
                <input
                  type="number"
                  className="admin-input"
                  value={billing.package_session_count}
                  onChange={(e) => setBill('package_session_count', e.target.value)}
                />
              </label>
              <label>
                Package amount (INR)
                <input
                  type="number"
                  className="admin-input"
                  value={billing.package_amount_inr}
                  onChange={(e) => setBill('package_amount_inr', e.target.value)}
                />
              </label>
            </>
          )}
        </div>
      ) : null}

      {mode === 'new' && createCase && step === 4 ? (
        <div style={{ maxWidth: 480 }}>
          <AdminTherapistPicker mode="allotment" productModule={productModule} value={therapistId} onChange={setTherapistId} />
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        {step > 1 && mode === 'new' ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setStep((s) => s - 1)}>
            Back
          </button>
        ) : null}
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={saving}
          onClick={handleNext}
        >
          {saving
            ? 'Saving…'
            : mode === 'link'
              ? 'Link parent'
              : step < totalSteps
                ? 'Next'
                : createCase
                  ? 'Create family & case'
                  : 'Create family'}
        </button>
      </div>
    </section>
  )
}

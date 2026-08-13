import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AddressFormFields, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { productRequiresDayType } from '../../lib/dayTypeLabels.js'

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

function isCompleteEmail(value) {
  const email = value.trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export function AdminAddFamilyWizard({ onComplete, onCancel }) {
  const [mode, setMode] = useState('new')
  const [step, setStep] = useState(1)
  const [createCase, setCreateCase] = useState(false)
  const [child, setChild] = useState(EMPTY_CHILD)
  const [parent, setParent] = useState(EMPTY_PARENT)
  const [parentSearch, setParentSearch] = useState('')
  const [parentMatches, setParentMatches] = useState([])
  const [existingParentId, setExistingParentId] = useState('')
  const [parentSelectionLocked, setParentSelectionLocked] = useState(false)
  const [lockedParentSnapshot, setLockedParentSnapshot] = useState(null)
  const [duplicateParentMatch, setDuplicateParentMatch] = useState(null)
  const [emailRoleError, setEmailRoleError] = useState('')
  const [checkingEmail, setCheckingEmail] = useState(false)
  const [productModule, setProductModule] = useState('homecare')
  const [dayType, setDayType] = useState('')
  const [caseCode, setCaseCode] = useState('')
  const [serviceType, setServiceType] = useState('Homecare')
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [billing, setBilling] = useState(EMPTY_BILLING)
  const [therapistId, setTherapistId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')

  const totalSteps = createCase ? 4 : 1

  const selectedParent = useMemo(() => {
    if (lockedParentSnapshot && String(lockedParentSnapshot.userId) === existingParentId) {
      return lockedParentSnapshot
    }
    return parentMatches.find((p) => String(p.userId) === existingParentId) || null
  }, [existingParentId, lockedParentSnapshot, parentMatches])

  const checkParentEmail = useCallback(async (rawEmail) => {
    const email = rawEmail.trim().toLowerCase()
    if (!isCompleteEmail(email)) {
      setDuplicateParentMatch(null)
      setEmailRoleError('')
      return
    }
    setCheckingEmail(true)
    setEmailRoleError('')
    setDuplicateParentMatch(null)
    try {
      const parents = await apiFetch(`/api/v1/admin/parents/lookup?search=${encodeURIComponent(email)}`)
      const list = Array.isArray(parents) ? parents : []
      const parentMatch = list.find((p) => (p.email || '').trim().toLowerCase() === email)
      if (parentMatch) {
        setDuplicateParentMatch(parentMatch)
        return
      }
      const users = await apiFetch(
        `/api/v1/admin/users/directory?search=${encodeURIComponent(email)}&limit=50`,
      )
      const userRows = Array.isArray(users) ? users : []
      const userMatch = userRows.find((u) => (u.email || '').trim().toLowerCase() === email)
      const roles = userMatch?.roles || []
      const isParent = roles.includes('PARENT')
      const isTherapist = roles.includes('THERAPIST')
      if (userMatch && isTherapist && !isParent) {
        setEmailRoleError('This email is a Therapist account. Use a different email.')
      }
    } catch {
      // Non-blocking — submit will still validate server-side.
    } finally {
      setCheckingEmail(false)
    }
  }, [])

  useEffect(() => {
    if (mode !== 'existing' || parentSelectionLocked) return
    const t = setTimeout(() => {
      const qs = parentSearch.trim() ? `?search=${encodeURIComponent(parentSearch.trim())}` : ''
      apiFetch(`/api/v1/admin/parents/lookup${qs}`)
        .then((rows) => setParentMatches(Array.isArray(rows) ? rows : []))
        .catch(() => setParentMatches([]))
    }, 300)
    return () => clearTimeout(t)
  }, [mode, parentSearch, parentSelectionLocked])

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

  function switchMode(nextMode) {
    setMode(nextMode)
    setStep(1)
    setError('')
    if (nextMode === 'new') {
      setParentSelectionLocked(false)
      setLockedParentSnapshot(null)
    }
  }

  function goToExistingParent(prefill) {
    setMode('existing')
    setStep(1)
    setError('')
    setEmailRoleError('')
    setDuplicateParentMatch(null)
    if (prefill) {
      setExistingParentId(String(prefill.userId))
      setParentSearch(prefill.email || '')
      setLockedParentSnapshot(prefill)
      setParentSelectionLocked(true)
      setParentMatches([prefill])
    }
  }

  function unlockParentSelection() {
    setParentSelectionLocked(false)
    setLockedParentSnapshot(null)
    if (selectedParent?.email) {
      setParentSearch(selectedParent.email)
    }
  }

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

  async function submitChildToExistingParent() {
    const res = await apiFetch('/api/v1/admin/children', {
      method: 'POST',
      body: JSON.stringify({
        parent_user_id: Number(existingParentId),
        first_name: child.first_name.trim(),
        last_name: child.last_name.trim(),
        date_of_birth: child.date_of_birth || null,
      }),
    })
    return res.id
  }

  async function submitAllot(childId) {
    const payload = {
      child_id: childId,
      service_type: serviceType.trim(),
      product_module: productModule,
      billing_type: billing.billing_type,
      client_billing_mode: billing.client_billing_mode,
      compensation_mode: billing.compensation_mode,
      pay_share_pct: Number(billing.pay_share_pct),
      therapist_user_id: Number(therapistId),
    }
    if (productRequiresDayType(productModule)) {
      payload.day_type = dayType
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
      if (!child.first_name.trim() || !child.last_name.trim()) {
        throw new Error('Child first and last name are required')
      }

      if (mode === 'existing') {
        if (!existingParentId) throw new Error('Select a parent account')
        const childId = await submitChildToExistingParent()
        if (createCase) {
          if (!therapistId) throw new Error('Select a therapist')
          if (productRequiresDayType(productModule) && !dayType) {
            throw new Error('Select half day or full day for this case')
          }
          const result = await submitAllot(childId)
          onComplete?.({ mode: 'existing', childId, case: result.case })
        } else {
          onComplete?.({ mode: 'existing', childId })
        }
        return
      }

      if (!parent.email.trim() || !parent.full_name.trim()) {
        throw new Error('Parent name and email are required')
      }
      if (emailRoleError) throw new Error(emailRoleError)
      if (duplicateParentMatch) {
        throw new Error(
          'This parent email is already registered. Use “Add child to existing parent” or choose a different email.',
        )
      }

      const childId = await submitFamily()
      if (createCase) {
        if (!therapistId) throw new Error('Select a therapist')
        if (productRequiresDayType(productModule) && !dayType) {
          throw new Error('Select half day or full day for this case')
        }
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
    if (step === 1 && !createCase) {
      handleFinish()
      return
    }
    if (step < totalSteps) setStep((s) => s + 1)
    else handleFinish()
  }

  const stepSubtitle =
    mode === 'existing'
      ? step === 1
        ? 'Add a child to an existing parent account'
        : `Step ${step} of ${totalSteps}`
      : `Step ${step} of ${totalSteps}`

  const primaryLabel =
    saving
      ? 'Saving…'
      : step < totalSteps
        ? 'Next'
        : mode === 'existing'
          ? createCase
            ? 'Add child & case'
            : 'Add child'
          : createCase
            ? 'Create family & case'
            : 'Create family'

  return (
    <section className="admin-panel" style={{ marginBottom: 20, padding: 16, border: '1px solid #e2e8f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <p className="admin-drawer__subtitle">Add family</p>
          <p className="admin-muted" style={{ fontSize: '0.85rem', margin: 0 }}>
            {stepSubtitle}
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
          { id: 'existing', label: 'Add child to existing parent' },
        ].map((m) => (
          <button
            key={m.id}
            type="button"
            className={`admin-btn admin-btn--sm ${mode === m.id ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => switchMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {emailRoleError ? <p className="admin-alert admin-alert--error">{emailRoleError}</p> : null}
      {inviteUrl ? (
        <p className="admin-alert admin-alert--success" style={{ wordBreak: 'break-all', fontSize: '0.85rem' }}>
          Parent invite link: {inviteUrl}
        </p>
      ) : null}

      {mode === 'new' && duplicateParentMatch ? (
        <div
          className="admin-alert"
          style={{
            marginBottom: 16,
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            color: '#1e3a8a',
          }}
        >
          <p style={{ margin: '0 0 8px', fontSize: '0.875rem' }}>
            <strong>{duplicateParentMatch.fullName}</strong> ({duplicateParentMatch.email}) is already registered as a
            parent. Add another child to this account?
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => goToExistingParent(duplicateParentMatch)}
            >
              Add child to existing parent
            </button>
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={() => {
                setDuplicateParentMatch(null)
                setParent((p) => ({ ...p, email: '' }))
              }}
            >
              Use a different email
            </button>
          </div>
        </div>
      ) : null}

      {mode === 'existing' && step === 1 ? (
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

          {parentSelectionLocked && selectedParent ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <p className="admin-drawer__subtitle" style={{ marginBottom: 6 }}>
                Parent account
              </p>
              <p className="admin-muted" style={{ margin: '0 0 8px', fontSize: '0.875rem' }}>
                {selectedParent.fullName} · {selectedParent.email}
                {selectedParent.children?.length
                  ? ` · ${selectedParent.children.length} child${selectedParent.children.length === 1 ? '' : 'ren'} on file`
                  : ''}
              </p>
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={unlockParentSelection}
              >
                Change parent
              </button>
            </div>
          ) : (
            <>
              <label style={{ gridColumn: '1 / -1' }}>
                Search parent email or name
                <input
                  className="admin-input"
                  value={parentSearch}
                  onChange={(e) => setParentSearch(e.target.value)}
                  placeholder="parent@example.com"
                />
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                Parent account
                <select
                  className="admin-input"
                  value={existingParentId}
                  onChange={(e) => setExistingParentId(e.target.value)}
                >
                  <option value="">Select parent…</option>
                  {parentMatches.map((p) => (
                    <option key={p.userId} value={p.userId}>
                      {p.fullName} · {p.email}
                      {p.children?.length ? ` (${p.children.length} children)` : ''}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

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
              onChange={(e) => {
                setParent((p) => ({ ...p, email: e.target.value }))
                if (duplicateParentMatch) setDuplicateParentMatch(null)
                if (emailRoleError) setEmailRoleError('')
              }}
              onBlur={() => checkParentEmail(parent.email)}
            />
            {checkingEmail ? (
              <span className="admin-muted" style={{ fontSize: '0.75rem' }}>
                Checking email…
              </span>
            ) : null}
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

      {createCase && step === 2 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Module
            <select className="admin-input" value={productModule} onChange={(e) => {
              setProductModule(e.target.value)
              setDayType('')
            }}>
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
          {productRequiresDayType(productModule) ? (
            <label>
              School day type
              <select className="admin-input" value={dayType} onChange={(e) => setDayType(e.target.value)} required>
                <option value="">Select half day or full day…</option>
                <option value="HALF_DAY">Half day</option>
                <option value="FULL_DAY">Full day</option>
              </select>
            </label>
          ) : null}
          {productModule === 'homecare' ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <p className="admin-drawer__subtitle">Service address (optional)</p>
              <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="fam-svc" showLocationButton={false} />
            </div>
          ) : null}
        </div>
      ) : null}

      {createCase && step === 3 ? (
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
                  min="50"
                  max="100"
                  step="0.01"
                  inputMode="decimal"
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

      {createCase && step === 4 ? (
        <div style={{ maxWidth: 480 }}>
          <AdminTherapistPicker mode="allotment" productModule={productModule} value={therapistId} onChange={setTherapistId} />
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        {step > 1 ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setStep((s) => s - 1)}>
            Back
          </button>
        ) : null}
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={saving || (mode === 'new' && !!emailRoleError)}
          onClick={handleNext}
        >
          {primaryLabel}
        </button>
      </div>
    </section>
  )
}

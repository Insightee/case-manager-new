import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AddressFormFields, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'

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

export function AdminCaseAllotmentWizard({ onComplete, onCancel }) {
  const { canCreateProductCase } = useModuleWrite()
  const [step, setStep] = useState(1)
  const [families, setFamilies] = useState([])
  const [familyMode, setFamilyMode] = useState('existing')
  const [childId, setChildId] = useState('')
  const [newChild, setNewChild] = useState({ first_name: '', last_name: '' })
  const [newParent, setNewParent] = useState({
    email: '',
    full_name: '',
    phone: '',
    send_invite: true,
  })
  const [productModule, setProductModule] = useState('homecare')
  const canSubmitAllot = canCreateProductCase(productModule)
  const [caseCode, setCaseCode] = useState('')
  const [serviceType, setServiceType] = useState('Homecare')
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [billing, setBilling] = useState(EMPTY_BILLING)
  const [therapistId, setTherapistId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [showQuickChild, setShowQuickChild] = useState(false)
  const [quickChild, setQuickChild] = useState({ first_name: '', last_name: '' })
  const [familySearch, setFamilySearch] = useState('')

  const filteredFamilies = useMemo(() => {
    const q = familySearch.trim().toLowerCase()
    const byId = new Map()
    for (const f of families) {
      if (!byId.has(f.childId)) byId.set(f.childId, f)
    }
    const unique = [...byId.values()]
    if (!q) return unique
    return unique.filter((f) => {
      const parentBit = (f.parents || []).map((p) => `${p.parentName} ${p.parentEmail}`).join(' ')
      const hay = `${f.childName} ${parentBit} ${(f.caseCodes || []).join(' ')}`.toLowerCase()
      return hay.includes(q)
    })
  }, [families, familySearch])

  const loadFamilies = useCallback(() => {
    apiFetch('/api/v1/admin/families')
      .then(setFamilies)
      .catch(() => setFamilies([]))
  }, [])

  useEffect(() => {
    loadFamilies()
  }, [loadFamilies])

  useEffect(() => {
    apiFetch(`/api/v1/admin/cases/next-code?product_module=${encodeURIComponent(productModule)}`)
      .then((r) => setCaseCode(r.case_code))
      .catch(() => setCaseCode(''))
  }, [productModule])

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

  async function ensureChildId() {
    if (familyMode === 'existing') {
      if (!childId) throw new Error('Select a child')
      return Number(childId)
    }
    if (!newChild.first_name.trim() || !newChild.last_name.trim()) {
      throw new Error('Child first and last name required')
    }
    if (!newParent.email.trim() || !newParent.full_name.trim()) {
      throw new Error('Parent name and email required for new families')
    }
    const fam = await apiFetch('/api/v1/admin/families', {
      method: 'POST',
      body: JSON.stringify({
        parent_email: newParent.email.trim(),
        parent_full_name: newParent.full_name.trim(),
        parent_phone: newParent.phone.trim() || null,
        child: {
          first_name: newChild.first_name.trim(),
          last_name: newChild.last_name.trim(),
        },
        send_invite: newParent.send_invite,
      }),
    })
    if (fam.inviteUrl) setInviteUrl(fam.inviteUrl)
    loadFamilies()
    return fam.childId
  }

  async function handleSubmit() {
    setSaving(true)
    setError('')
    try {
      const cid = await ensureChildId()
      const payload = {
        child_id: cid,
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
        if (billing.compensation_mode === 'FIXED_LUMP') {
          payload.therapist_fixed_pay_inr = Number(billing.therapist_fixed_pay_inr)
        }
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
      const result = await apiFetch('/api/v1/admin/cases/allot', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onComplete?.(result.case, inviteUrl)
    } catch (err) {
      setError(err.message || 'Allotment failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="admin-panel" style={{ marginBottom: 20, padding: 16 }}>
      <p className="admin-drawer__subtitle">Case allotment — step {step} of 4</p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {inviteUrl ? (
        <p style={{ fontSize: '0.875rem', color: '#047857', wordBreak: 'break-all' }}>
          Parent invite: {inviteUrl}
        </p>
      ) : null}

      {step === 1 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <fieldset style={{ gridColumn: '1 / -1', border: 'none', padding: 0, margin: 0 }}>
            <legend className="text-sm font-semibold text-slate-700 mb-3">Client type</legend>
            <div className="flex gap-4">
              {[
                { id: 'existing', label: 'Existing client' },
                { id: 'new', label: 'New client' },
              ].map((opt) => (
                <label key={opt.id} className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="familyMode"
                    checked={familyMode === opt.id}
                    onChange={() => setFamilyMode(opt.id)}
                    className="h-4 w-4 accent-indigo-600 flex-shrink-0"
                  />
                  <span className="text-sm text-slate-700">{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {familyMode === 'existing' ? (
            <>
              <label style={{ gridColumn: '1 / -1' }}>
                Search child or parent
                <input
                  className="admin-input"
                  type="search"
                  placeholder="Name, email, or case code…"
                  value={familySearch}
                  onChange={(e) => setFamilySearch(e.target.value)}
                />
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                Child
                <select className="admin-input" value={childId} onChange={(e) => setChildId(e.target.value)} required>
                  <option value="">
                    {filteredFamilies.length ? 'Select child…' : 'No matches — add a child below'}
                  </option>
                  {filteredFamilies.map((f) => (
                    <option key={f.childId} value={f.childId}>
                      {f.childName} (#{f.childId})
                      {f.parents?.[0]?.parentEmail ? ` · ${f.parents[0].parentEmail}` : ' · no parent linked'}
                      {f.caseCodes?.length ? ` · ${f.caseCodes.join(', ')}` : ''}
                    </option>
                  ))}
                </select>
              </label>
              {families.length > 0 && filteredFamilies.length === 0 ? (
                <p style={{ gridColumn: '1 / -1', fontSize: '0.8rem', color: '#b45309' }}>
                  No children match your search. Try another term or add a new child.
                </p>
              ) : null}
              <div style={{ gridColumn: '1 / -1' }}>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  onClick={() => setShowQuickChild((v) => !v)}
                >
                  {showQuickChild ? 'Cancel' : '+ Add child'}
                </button>
                {showQuickChild ? (
                  <div className="admin-form-grid" style={{ marginTop: 8, maxWidth: 400 }}>
                    <label>
                      First name
                      <input
                        className="admin-input"
                        value={quickChild.first_name}
                        onChange={(e) => setQuickChild((c) => ({ ...c, first_name: e.target.value }))}
                      />
                    </label>
                    <label>
                      Last name
                      <input
                        className="admin-input"
                        value={quickChild.last_name}
                        onChange={(e) => setQuickChild((c) => ({ ...c, last_name: e.target.value }))}
                      />
                    </label>
                    <button
                      type="button"
                      className="admin-btn admin-btn--secondary admin-btn--sm"
                      onClick={async () => {
                        setError('')
                        try {
                          const res = await apiFetch('/api/v1/admin/children', {
                            method: 'POST',
                            body: JSON.stringify({
                              first_name: quickChild.first_name.trim(),
                              last_name: quickChild.last_name.trim(),
                            }),
                          })
                          loadFamilies()
                          setChildId(String(res.id))
                          setShowQuickChild(false)
                          setQuickChild({ first_name: '', last_name: '' })
                        } catch (err) {
                          setError(err.message || 'Could not add child')
                        }
                      }}
                    >
                      Save child
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <label>
                Child first name
                <input className="admin-input" value={newChild.first_name} onChange={(e) => setNewChild((c) => ({ ...c, first_name: e.target.value }))} />
              </label>
              <label>
                Child last name
                <input className="admin-input" value={newChild.last_name} onChange={(e) => setNewChild((c) => ({ ...c, last_name: e.target.value }))} />
              </label>
              <label>
                Parent name
                <input className="admin-input" value={newParent.full_name} onChange={(e) => setNewParent((p) => ({ ...p, full_name: e.target.value }))} />
              </label>
              <label>
                Parent email
                <input type="email" className="admin-input" value={newParent.email} onChange={(e) => setNewParent((p) => ({ ...p, email: e.target.value }))} />
              </label>
              <label>
                Parent phone
                <input className="admin-input" value={newParent.phone} onChange={(e) => setNewParent((p) => ({ ...p, phone: e.target.value }))} />
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                <input
                  type="checkbox"
                  checked={newParent.send_invite}
                  onChange={(e) => setNewParent((p) => ({ ...p, send_invite: e.target.checked }))}
                />{' '}
                Send portal invite email (link shown after submit)
              </label>
            </>
          )}
        </div>
      ) : null}

      {step === 2 ? (
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
            <input className="admin-input" list="service-presets" value={serviceType} onChange={(e) => setServiceType(e.target.value)} />
            <datalist id="service-presets">
              {(SERVICE_PRESETS[productModule] || []).map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </label>
          {productModule === 'homecare' ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <p className="admin-drawer__subtitle">Service address (optional)</p>
              <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="wiz-svc" showLocationButton={false} />
            </div>
          ) : null}
        </div>
      ) : null}

      {step === 3 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Client billing (family invoice)
            <select className="admin-input" value={billing.client_billing_mode} onChange={(e) => setBill('client_billing_mode', e.target.value)}>
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
                <input type="number" className="admin-input" value={billing.client_rate_per_session_inr} onChange={(e) => setBill('client_rate_per_session_inr', e.target.value)} />
              </label>
              <label>
                Therapist share %
                <input type="number" min="50" max="70" className="admin-input" value={billing.pay_share_pct} onChange={(e) => setBill('pay_share_pct', e.target.value)} />
              </label>
            </>
          ) : (
            <>
              <label>
                Package sessions
                <input type="number" className="admin-input" value={billing.package_session_count} onChange={(e) => setBill('package_session_count', e.target.value)} />
              </label>
              <label>
                Package amount (INR)
                <input type="number" className="admin-input" value={billing.package_amount_inr} onChange={(e) => setBill('package_amount_inr', e.target.value)} />
              </label>
              <label>
                Therapist share %
                <input type="number" min="50" max="70" className="admin-input" value={billing.pay_share_pct} onChange={(e) => setBill('pay_share_pct', e.target.value)} />
              </label>
            </>
          )}
        </div>
      ) : null}

      {step === 4 ? (
        <div style={{ maxWidth: 480 }}>
          <p className="text-sm font-semibold text-slate-700 mb-1">Assign therapist</p>
          <p className="text-xs text-slate-500 mb-3">
            Only therapists approved for {productModule.replace(/_/g, ' ')} are listed.
          </p>
          <AdminTherapistPicker
            mode="allotment"
            productModule={productModule}
            value={therapistId}
            onChange={setTherapistId}
          />
          {therapistId && (
            <p className="mt-3 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              Therapist selected — click <strong>Create case &amp; assign</strong> to proceed.
            </p>
          )}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        {step > 1 ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setStep((s) => s - 1)}>
            Back
          </button>
        ) : (
          onCancel && (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onCancel}>
              Cancel
            </button>
          )
        )}
        {step < 4 ? (
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setStep((s) => s + 1)}>
            Next
          </button>
        ) : (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={saving || !therapistId || !canSubmitAllot}
            onClick={handleSubmit}
          >
            {saving ? 'Creating…' : 'Create case & assign'}
          </button>
        )}
        {step === 4 && !canSubmitAllot ? (
          <p className="admin-muted" style={{ width: '100%', fontSize: '0.8rem' }}>
            You have view-only access for {productModule.replace(/_/g, ' ')} — cannot allot new cases.
          </p>
        ) : null}
      </div>
    </section>
  )
}

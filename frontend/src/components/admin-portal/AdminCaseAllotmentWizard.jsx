import { useCallback, useEffect, useMemo, useState } from 'react'
import { formatSessionWhen } from '../../lib/sessionDisplay.js'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AddressFormFields, addressFromApi, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AdminFamilyCombobox } from './AdminFamilyCombobox.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { CaseSchedulingHub } from './CaseSchedulingHub.jsx'
import { useClinicalProductModules } from '../../hooks/useClinicalProductModules.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import './admin-allotment-wizard.css'

const TOTAL_STEPS = 5

const EMPTY_BILLING = {
  billing_type: 'PER_SESSION',
  client_billing_mode: 'POSTPAID',
  client_rate_per_session_inr: '1000',
  pay_share_pct: '60',
  package_session_count: '12',
  package_amount_inr: '12000',
  compensation_mode: 'PERCENTAGE',
  therapist_fixed_pay_inr: '',
  product_billing_rule_id: '',
}

export function AdminCaseAllotmentWizard({ onComplete, onCancel }) {
  const { user } = useAuth()
  const { canCreateProductCase } = useModuleWrite()
  const [step, setStep] = useState(1)
  const [familyMode, setFamilyMode] = useState('existing')
  const [childId, setChildId] = useState('')
  const [selectedFamily, setSelectedFamily] = useState(null)
  const [newChild, setNewChild] = useState({ first_name: '', last_name: '' })
  const [parentIsExisting, setParentIsExisting] = useState(false)
  const [existingParentId, setExistingParentId] = useState('')
  const [parentSearch, setParentSearch] = useState('')
  const [parentMatches, setParentMatches] = useState([])
  const [newParent, setNewParent] = useState({
    email: '',
    full_name: '',
    phone: '',
    send_invite: true,
  })
  const { options: clinicalOptions } = useClinicalProductModules()
  const moduleOptions = useMemo(
    () => clinicalOptions.filter((o) => o.value).map((o) => ({ id: o.value, label: o.label })),
    [clinicalOptions],
  )
  const [productModule, setProductModule] = useState('homecare')
  const canSubmitAllot = canCreateProductCase(productModule)
  const [caseCode, setCaseCode] = useState('')
  const [serviceType, setServiceType] = useState('')
  const [serviceCategories, setServiceCategories] = useState([])
  const [clinicalCatalog, setClinicalCatalog] = useState([])
  const [serviceProductId, setServiceProductId] = useState('')
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [addressSource, setAddressSource] = useState('manual')
  const [billing, setBilling] = useState(EMPTY_BILLING)
  const [therapistId, setTherapistId] = useState('')
  const [therapistLabel, setTherapistLabel] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [createdCase, setCreatedCase] = useState(null)
  const [createdAssignments, setCreatedAssignments] = useState([])
  const [scheduledSessionCount, setScheduledSessionCount] = useState(0)
  const [previewData, setPreviewData] = useState(null)
  const [activating, setActivating] = useState(false)
  const [activationInvites, setActivationInvites] = useState([])

  useEffect(() => {
    apiFetch('/api/v1/admin/service-categories')
      .then((rows) => {
        const active = (rows || []).filter((r) => r.is_active !== false)
        setServiceCategories(active)
        if (active.length && !serviceType) setServiceType(active[0].label)
      })
      .catch(() => setServiceCategories([]))
    apiFetch('/api/v1/auth/catalog/clinical-services')
      .then((rows) => setClinicalCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setClinicalCatalog([]))
  }, [])

  const productsForModule = useMemo(() => {
    const cat = clinicalCatalog.find((c) => c.id === productModule)
    return (cat?.products || []).filter((p) => p.active !== false)
  }, [clinicalCatalog, productModule])

  useEffect(() => {
    const cat = serviceCategories.find((c) => c.id === productModule)
    if (cat?.label) setServiceType(cat.label)
    setServiceProductId('')
  }, [productModule, serviceCategories])

  useEffect(() => {
    if (!serviceProductId) return
    const product = productsForModule.find((p) => String(p.id) === String(serviceProductId))
    if (!product) return
    const model = (product.billing_model || 'PER_SESSION').toUpperCase()
    const isPackage = model.includes('PACKAGE') || model.includes('PREPAID')
    setBilling((b) => ({
      ...b,
      product_billing_rule_id: product.product_billing_rule_id
        ? String(product.product_billing_rule_id)
        : '',
      billing_type: isPackage ? 'PACKAGE' : 'PER_SESSION',
      client_billing_mode: isPackage ? 'PREPAID' : 'POSTPAID',
      client_rate_per_session_inr:
        product.price_inr != null ? String(product.price_inr) : b.client_rate_per_session_inr,
      package_session_count:
        product.package_sessions != null ? String(product.package_sessions) : b.package_session_count,
      package_amount_inr: product.total_inr != null ? String(product.total_inr) : b.package_amount_inr,
    }))
  }, [serviceProductId, productsForModule])

  useEffect(() => {
    if (familyMode !== 'new' || !parentIsExisting) return
    const t = setTimeout(() => {
      const qs = parentSearch.trim() ? `?search=${encodeURIComponent(parentSearch.trim())}` : ''
      apiFetch(`/api/v1/admin/parents/lookup${qs}`)
        .then(setParentMatches)
        .catch(() => setParentMatches([]))
    }, 300)
    return () => clearTimeout(t)
  }, [parentSearch, parentIsExisting, familyMode])

  useEffect(() => {
    apiFetch(`/api/v1/admin/cases/next-code?product_module=${encodeURIComponent(productModule)}`)
      .then((r) => setCaseCode(r.case_code))
      .catch(() => setCaseCode(''))
  }, [productModule])

  useEffect(() => {
    if (!therapistId || !productModule) {
      setTherapistLabel('')
      return
    }
    apiFetch(
      `/api/v1/admin/allotment/therapists?product_module=${encodeURIComponent(productModule)}&approved_only=false`,
    )
      .then((rows) => {
        const match = (rows || []).find((t) => String(t.therapist_user_id) === String(therapistId))
        if (match) {
          setTherapistLabel(`${match.therapist_name || match.full_name} · ${match.email || ''}`.trim())
        } else {
          setTherapistLabel(`Therapist #${therapistId}`)
        }
      })
      .catch(() => setTherapistLabel(`Therapist #${therapistId}`))
  }, [therapistId, productModule])

  useEffect(() => {
    if (!moduleOptions.find((m) => m.id === productModule) && moduleOptions.length) {
      setProductModule(moduleOptions[0].id)
    }
  }, [moduleOptions, productModule])

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
    if (parentIsExisting && existingParentId) {
      const res = await apiFetch('/api/v1/admin/children', {
        method: 'POST',
        body: JSON.stringify({
          parent_user_id: Number(existingParentId),
          first_name: newChild.first_name.trim(),
          last_name: newChild.last_name.trim(),
        }),
      })
      return res.id
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
      if (billing.product_billing_rule_id) {
        payload.product_billing_rule_id = Number(billing.product_billing_rule_id)
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
      if (serviceAddr.address_line1) {
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
      setCreatedCase(result.case)
      const asg = await apiFetch(`/api/v1/cases/${result.case.id}/assignments`).catch(() => [])
      setCreatedAssignments(asg || [])
      setScheduledSessionCount(0)
      setPreviewData(null)
      setStep(5)
    } catch (err) {
      setError(err.message || 'Allotment failed')
    } finally {
      setSaving(false)
    }
  }

  const loadPreview = useCallback(async () => {
    if (!createdCase?.id) return
    const data = await apiFetch(`/api/v1/admin/cases/${createdCase.id}/allotment-preview`)
    setPreviewData(data)
    const sessions = data.upcoming_sessions || []
    setScheduledSessionCount(sessions.length)
  }, [createdCase?.id])

  useEffect(() => {
    if (step === 6 && createdCase?.id) {
      loadPreview().catch((err) => setError(err.message || 'Could not load preview'))
    }
  }, [step, createdCase?.id, loadPreview])

  async function handleApprove() {
    if (!createdCase?.id) return
    setActivating(true)
    setError('')
    try {
      const res = await apiFetch(`/api/v1/admin/cases/${createdCase.id}/activate-allotment`, {
        method: 'POST',
        timeoutMs: 120_000,
      })
      setCreatedCase(res.case)
      setActivationInvites(res.parent_invite_urls || [])
      if (res.parent_invite_urls?.length) {
        setInviteUrl(res.parent_invite_urls[0])
      }
      setStep(7)
    } catch (err) {
      setError(err.message || 'Activation failed')
    } finally {
      setActivating(false)
    }
  }

  return (
    <section className="admin-panel" style={{ marginBottom: 20, padding: 16 }}>
      <p className="admin-drawer__subtitle">Case allotment — step {step} of {TOTAL_STEPS}</p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {inviteUrl ? (
        <p style={{ fontSize: '0.875rem', color: '#047857', wordBreak: 'break-all' }}>
          Parent invite: {inviteUrl}
        </p>
      ) : null}

      {step === 1 ? (
        <div className="admin-form-grid admin-allotment-wizard__form">
          <fieldset className="admin-allotment-wizard__client-type">
            <legend className="text-sm font-semibold text-slate-700 mb-3">Client type</legend>
            <div className="admin-allotment-wizard__client-type-options">
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
            <label className="admin-allotment-wizard__search-field">
              Search child or parent
              <AdminFamilyCombobox
                value={childId}
                onChange={setChildId}
                onSelectFamily={setSelectedFamily}
              />
            </label>
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
              <label style={{ gridColumn: '1 / -1' }}>
                <input
                  type="checkbox"
                  checked={parentIsExisting}
                  onChange={(e) => setParentIsExisting(e.target.checked)}
                />{' '}
                Link to existing parent account
              </label>
              {parentIsExisting ? (
                <>
                  <label style={{ gridColumn: '1 / -1' }}>
                    Search parent email or name
                    <input
                      className="admin-input"
                      value={parentSearch}
                      onChange={(e) => setParentSearch(e.target.value)}
                      placeholder="parent@email.com"
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
                          {p.fullName} · {p.email} ({p.children?.length || 0} children)
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : (
                <>
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
            </>
          )}
        </div>
      ) : null}

      {step === 2 ? (
        <div className="admin-form-grid" style={{ maxWidth: 520 }}>
          <label>
            Module
            <select className="admin-input" value={productModule} onChange={(e) => setProductModule(e.target.value)}>
              {moduleOptions.map((m) => (
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
            <select className="admin-input" value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
              {serviceCategories.map((c) => (
                <option key={c.id} value={c.label}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          {productsForModule.length > 0 ? (
            <label style={{ gridColumn: '1 / -1' }}>
              Commercial product (billing rule)
              <select
                className="admin-input"
                value={serviceProductId}
                onChange={(e) => setServiceProductId(e.target.value)}
              >
                <option value="">Select product (optional)…</option>
                {productsForModule.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.billing_model}
                    {p.price_inr != null ? ` · ₹${p.price_inr}` : ''}
                  </option>
                ))}
              </select>
              <span className="admin-muted" style={{ fontSize: '0.75rem' }}>
                Prefills client billing and links the ledger rule from Settings.
              </span>
            </label>
          ) : null}
          <div style={{ gridColumn: '1 / -1' }}>
            <p className="admin-drawer__subtitle">Service address (optional)</p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
              {['manual', 'parent_home'].map((src) => (
                <label key={src} style={{ fontSize: '0.85rem' }}>
                  <input
                    type="radio"
                    name="addrSrc"
                    checked={addressSource === src}
                    onChange={() => setAddressSource(src)}
                  />{' '}
                  {src === 'manual' ? 'Enter manually' : 'Copy parent home (when available)'}
                </label>
              ))}
            </div>
            {addressSource === 'parent_home' && selectedFamily?.parents?.[0]?.userId ? (
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                style={{ marginBottom: 8 }}
                onClick={async () => {
                  try {
                    const rows = await apiFetch(
                      `/api/v1/admin/families?search=${encodeURIComponent(selectedFamily.parents[0].parentEmail || '')}`,
                    )
                    const match = (rows || []).find((r) => r.childId === Number(childId))
                    if (match?.parents?.[0]?.userId) {
                      const u = await apiFetch(`/api/v1/admin/users/${match.parents[0].userId}`).catch(() => null)
                      if (u?.home_address) setServiceAddr(addressFromApi(u.home_address))
                    }
                  } catch {
                    setError('Could not load parent address')
                  }
                }}
              >
                Load parent home address
              </button>
            ) : null}
            <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="wiz-svc" showLocationButton={false} />
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="admin-allotment-wizard__billing">
          <section className="admin-allotment-wizard__billing-section">
            <h3 className="admin-allotment-wizard__section-title">Assign therapist</h3>
            <p className="admin-allotment-wizard__section-lead">
              Choose who will deliver this case for {productModule.replace(/_/g, ' ')}. Billing rates apply to this
              therapist.
            </p>
            <AdminTherapistPicker
              mode="allotment"
              productModule={productModule}
              value={therapistId}
              onChange={setTherapistId}
            />
          </section>

          <section className="admin-allotment-wizard__billing-section admin-allotment-wizard__billing-rates">
            <h3 className="admin-allotment-wizard__section-title">Client &amp; therapist billing</h3>
            {!therapistId ? (
              <p className="admin-allotment-wizard__section-lead admin-allotment-wizard__section-lead--warn">
                Select a therapist above to set invoice type, package or per-session rates, and pay share.
              </p>
            ) : (
              <p className="admin-allotment-wizard__section-lead">
                Set what the family is charged and this therapist&apos;s pay share on the case.
              </p>
            )}
            <div className="admin-form-grid admin-allotment-wizard__billing-grid">
              <label>
                Client billing (family invoice)
                <select
                  className="admin-input"
                  value={billing.client_billing_mode}
                  onChange={(e) => setBill('client_billing_mode', e.target.value)}
                  disabled={!therapistId}
                >
                  <option value="POSTPAID">Postpaid</option>
                  <option value="PREPAID">Prepaid</option>
                </select>
              </label>
              <label>
                Therapist billing
                <select
                  className="admin-input"
                  value={billing.billing_type}
                  onChange={(e) => setBill('billing_type', e.target.value)}
                  disabled={!therapistId}
                >
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
                      disabled={!therapistId}
                    />
                  </label>
                  <label>
                    Therapist pay share %
                    <input
                      type="number"
                      min="50"
                      max="70"
                      className="admin-input"
                      value={billing.pay_share_pct}
                      onChange={(e) => setBill('pay_share_pct', e.target.value)}
                      disabled={!therapistId}
                    />
                    <span className="admin-muted" style={{ fontSize: '0.75rem', fontWeight: 400 }}>
                      Share of client session fee paid to the assigned therapist (typically 50–70%).
                    </span>
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
                      disabled={!therapistId}
                    />
                  </label>
                  <label>
                    Package amount (INR)
                    <input
                      type="number"
                      className="admin-input"
                      value={billing.package_amount_inr}
                      onChange={(e) => setBill('package_amount_inr', e.target.value)}
                      disabled={!therapistId}
                    />
                  </label>
                  <label>
                    Therapist pay share %
                    <input
                      type="number"
                      min="50"
                      max="70"
                      className="admin-input"
                      value={billing.pay_share_pct}
                      onChange={(e) => setBill('pay_share_pct', e.target.value)}
                      disabled={!therapistId}
                    />
                    <span className="admin-muted" style={{ fontSize: '0.75rem', fontWeight: 400 }}>
                      Percentage of package value for therapist payout.
                    </span>
                  </label>
                </>
              )}
            </div>
          </section>
        </div>
      ) : null}

      {step === 4 ? (
        <div className="admin-allotment-wizard__review">
          <h3 className="admin-allotment-wizard__section-title">Save draft case</h3>
          <p className="admin-allotment-wizard__section-lead">
            The case stays in pending allotment until you approve and send invites. You can schedule sessions next.
          </p>
          <dl className="admin-allotment-wizard__review-list">
            <div>
              <dt>Module</dt>
              <dd>{moduleOptions.find((m) => m.id === productModule)?.label || productModule}</dd>
            </div>
            <div>
              <dt>Case code</dt>
              <dd>{caseCode || '—'}</dd>
            </div>
            <div>
              <dt>Therapist</dt>
              <dd>{therapistLabel || (therapistId ? `Therapist #${therapistId}` : 'Not selected')}</dd>
            </div>
            <div>
              <dt>Client billing</dt>
              <dd>{billing.client_billing_mode}</dd>
            </div>
            <div>
              <dt>Therapist billing</dt>
              <dd>
                {billing.billing_type === 'PER_SESSION'
                  ? `Per session · ₹${billing.client_rate_per_session_inr}/session · ${billing.pay_share_pct}% pay share`
                  : `Package · ${billing.package_session_count} sessions · ₹${billing.package_amount_inr} · ${billing.pay_share_pct}% pay share`}
              </dd>
            </div>
          </dl>
          {!therapistId ? (
            <p className="admin-allotment-wizard__section-lead admin-allotment-wizard__section-lead--warn">
              Go back to step 3 and select a therapist.
            </p>
          ) : null}
        </div>
      ) : null}

      {step === 5 && createdCase ? (
        <div>
          <p className="admin-muted" style={{ marginBottom: 12 }}>
            Case {createdCase.case_code} (draft). Book recurring or one-off sessions — upcoming count:{' '}
            {scheduledSessionCount}.
          </p>
          <CaseSchedulingHub
            caseItem={createdCase}
            assignments={createdAssignments}
            onDone={loadPreview}
            onSessionsChange={(list) => setScheduledSessionCount(list.length)}
          />
        </div>
      ) : null}

      {step === 6 && createdCase ? (
        <div className="admin-allotment-wizard__preview">
          <h3 className="admin-allotment-wizard__section-title">Preview before approval</h3>
          <p className="admin-allotment-wizard__section-lead">
            After approval, parent and therapist receive invites to review the plan. Service can begin once the case
            is active — acceptance is optional during the pilot. Conflicts can be raised via Support.
          </p>
          <dl className="admin-allotment-wizard__review-list">
            <div>
              <dt>Case</dt>
              <dd>{createdCase.case_code}</dd>
            </div>
            <div>
              <dt>Therapist</dt>
              <dd>{previewData?.therapist_name || therapistLabel || '—'}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{previewData?.case?.status || createdCase.status || 'PENDING_ALLOTMENT'}</dd>
            </div>
            {previewData?.billing_summary ? (
              <div>
                <dt>Billing</dt>
                <dd>
                  {previewData.billing_summary.billing_type === 'PER_SESSION'
                    ? `Per session · ₹${previewData.billing_summary.client_rate_per_session_inr} · ${previewData.billing_summary.pay_share_pct}% pay share`
                    : `Package · ${previewData.billing_summary.package_session_count} sessions · ₹${previewData.billing_summary.package_amount_inr}`}
                </dd>
              </div>
            ) : null}
          </dl>
          <h4 className="admin-allotment-wizard__preview-sessions-title">Upcoming sessions</h4>
          {(previewData?.upcoming_sessions || []).length === 0 ? (
            <p className="admin-muted">No upcoming sessions scheduled yet. Go back to step 5 to book, or approve without sessions.</p>
          ) : (
            <table className="admin-allotment-wizard__sessions-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(previewData?.upcoming_sessions || []).map((s) => (
                  <tr key={s.id}>
                    <td>{formatSessionWhen(s)}</td>
                    <td>{s.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {step === 7 && createdCase ? (
        <div className="admin-allotment-wizard__success">
          <h3 className="admin-allotment-wizard__section-title">Case activated</h3>
          <p className="admin-allotment-wizard__section-lead">
            {createdCase.case_code} is active. Parent and therapist have been notified to accept the assignment.
          </p>
          {activationInvites.length > 0 ? (
            <p style={{ fontSize: '0.875rem', color: '#047857', wordBreak: 'break-all' }}>
              Parent invite: {activationInvites[0]}
            </p>
          ) : inviteUrl ? (
            <p style={{ fontSize: '0.875rem', color: '#047857', wordBreak: 'break-all' }}>
              Parent invite: {inviteUrl}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="admin-allotment-wizard__actions">
        {step > 1 && step < 7 && step !== 6 ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setStep((s) => s - 1)}>
            Back
          </button>
        ) : (
          onCancel && step < 5 && (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onCancel}>
              Cancel
            </button>
          )
        )}
        {step === 6 ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setStep(3)}>
            Back to edit
          </button>
        ) : null}
        {step < 3 ? (
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setStep((s) => s + 1)}>
            Next
          </button>
        ) : null}
        {step === 3 ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={!therapistId}
            onClick={() => {
              if (!therapistId) {
                setError('Select a therapist before continuing')
                return
              }
              setError('')
              setStep(4)
            }}
          >
            Next
          </button>
        ) : null}
        {step === 4 ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={saving || !therapistId || !canSubmitAllot}
            onClick={handleSubmit}
          >
            {saving ? 'Saving…' : 'Save draft & continue'}
          </button>
        ) : null}
        {step === 5 ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            onClick={() => {
              setError('')
              loadPreview()
                .then(() => setStep(6))
                .catch((err) => setError(err.message || 'Could not load preview'))
            }}
          >
            Continue to preview
          </button>
        ) : null}
        {step === 6 ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={activating}
            onClick={handleApprove}
          >
            {activating ? 'Approving…' : 'Approve & send invites'}
          </button>
        ) : null}
        {step === 7 ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            onClick={() => onComplete?.(createdCase, inviteUrl)}
          >
            Done
          </button>
        ) : null}
        {step === 4 && !canSubmitAllot ? (
          <p className="admin-muted" style={{ width: '100%', fontSize: '0.8rem' }}>
            You have view-only access for {productModule.replace(/_/g, ' ')} — cannot allot new cases.
          </p>
        ) : null}
      </div>
    </section>
  )
}

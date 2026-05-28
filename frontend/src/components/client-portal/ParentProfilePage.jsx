import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'
import { AvatarUpload } from '../shared/AvatarUpload.jsx'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import {
  AddressFormFields,
  addressFromApi,
  addressToPayload,
  emptyAddress,
  hasCoordinates,
} from '../shared/AddressFormFields.jsx'
import './parent-profile.css'

function dedupeChildren(list) {
  const byId = new Map()
  for (const c of list || []) {
    if (c?.id != null) byId.set(c.id, c)
  }
  return [...byId.values()]
}

function splitFullName(name) {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return { first: parts[0], last: '' }
  return { first: parts[0], last: parts.slice(1).join(' ') }
}

// ── Child row ──────────────────────────────────────────────────────────────
function ChildRow({ child, caseService, onEditSave }) {
  const [editing, setEditing] = useState(false)
  const [firstName, setFirstName] = useState(child.first_name)
  const [lastName, setLastName] = useState(child.last_name)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const fullName = [child.first_name, child.last_name].filter(Boolean).join(' ')

  async function save() {
    if (!firstName.trim()) return
    setSaving(true)
    setErr('')
    try {
      await onEditSave(child.id, firstName.trim(), lastName.trim())
      setEditing(false)
    } catch (e) {
      setErr(e.message || 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="parent-profile__child-row">
      <div className="parent-profile__child-info">
        <span className="parent-profile__child-name">{fullName || '—'}</span>
        {caseService ? (
          <div className="parent-profile__child-cases">
            {caseService.map((s) => (
              <span key={s.case_id} className="parent-profile__case-chip">
                {s.case_code}
                <span className="parent-profile__case-type">{s.service_type}</span>
              </span>
            ))}
          </div>
        ) : (
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>No case assigned yet</span>
        )}
      </div>

      <div className="parent-profile__child-actions">
        {caseService?.[0] ? (
          <Link to={`/parent/cases/${caseService[0].case_id}`} className="parent-profile__child-link">
            View case →
          </Link>
        ) : null}
        <button
          type="button"
          className="parent-profile__child-edit-btn"
          onClick={() => { setEditing((e) => !e); setErr('') }}
          title="Edit name"
        >
          ✏
        </button>
      </div>

      {editing ? (
        <div className="parent-profile__child-edit-form">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="First name"
              style={{ flex: 1, minWidth: 100, border: '1px solid #cbd5e1', borderRadius: 8, padding: '7px 10px', fontSize: '0.875rem' }}
            />
            <input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Last name"
              style={{ flex: 1, minWidth: 100, border: '1px solid #cbd5e1', borderRadius: 8, padding: '7px 10px', fontSize: '0.875rem' }}
            />
          </div>
          {err ? <p style={{ fontSize: '0.78rem', color: '#b91c1c', marginTop: 4 }}>{err}</p> : null}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button
              type="button"
              disabled={saving}
              onClick={save}
              style={{ background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 8, padding: '6px 16px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(false); setFirstName(child.first_name); setLastName(child.last_name) }}
              style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

// ── Add child inline form ──────────────────────────────────────────────────
function AddChildForm({ onAdd, onCancel }) {
  const [fullName, setFullName] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  async function submit(e) {
    e.preventDefault()
    if (!fullName.trim()) { setErr('Name is required'); return }
    setSaving(true)
    setErr('')
    try {
      await onAdd(fullName.trim())
    } catch (ex) {
      setErr(ex.message || 'Could not add child')
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="parent-profile__add-child-form">
      <input
        autoFocus
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        placeholder="Child's full name"
        style={{ flex: 1, border: '1px solid #cbd5e1', borderRadius: 8, padding: '8px 12px', fontSize: '0.875rem' }}
      />
      {err ? <p style={{ fontSize: '0.78rem', color: '#b91c1c', marginTop: 4, width: '100%' }}>{err}</p> : null}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button
          type="submit"
          disabled={saving}
          style={{ background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 8, padding: '7px 18px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
        >
          {saving ? 'Adding…' : 'Add'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: '7px 14px', fontSize: '0.85rem', cursor: 'pointer' }}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function ProfileLoadingSkeleton() {
  return (
    <div className="parent-profile parent-profile--loading" aria-busy="true" aria-label="Loading profile">
      <div className="parent-profile__skeleton parent-profile__skeleton--avatar" />
      <div className="parent-profile__skeleton parent-profile__skeleton--card" />
      <div className="parent-profile__skeleton parent-profile__skeleton--card parent-profile__skeleton--tall" />
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export function ParentProfilePage() {
  const { user, reload: reloadAuth } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [children, setChildren] = useState([])
  const [services, setServices] = useState([])
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [addressType, setAddressType] = useState('home') // 'home' | 'school'
  const [billingSame, setBillingSame] = useState(true)
  const [billingAddr, setBillingAddr] = useState(emptyAddress())
  const [homecareCases, setHomecareCases] = useState([])
  const [showAddChild, setShowAddChild] = useState(false)

  const loadProfile = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const p = await apiFetch('/api/v1/parent/profile', { timeoutMs: 45_000 })
      setFullName(p.full_name || '')
      setEmail(p.email || '')
      setPhone(p.phone || '')
      setChildren(
        dedupeChildren(p.children).map((c) => ({
          id: c.id,
          first_name: c.first_name,
          last_name: c.last_name,
        })),
      )
      setServices(p.services || [])
      setAddressType(p.address_type || 'home')
      const hc = p.homecare_cases || []
      setHomecareCases(hc)
      // Prefer the homecare service address if one exists, otherwise fall back to home_address
      const primaryAddr = hc.length ? hc[0].service_address : p.home_address
      setServiceAddr(addressFromApi(primaryAddr))
      if (p.billing_address_line1) {
        setBillingSame(false)
        setBillingAddr(addressFromApi({
          address_line1: p.billing_address_line1,
          address_line2: p.billing_address_line2,
          city: p.billing_city,
          state: p.billing_state,
          pincode: p.billing_pincode,
          landmark: p.billing_landmark,
          latitude: p.billing_latitude,
          longitude: p.billing_longitude,
        }))
      } else {
        setBillingSame(true)
        setBillingAddr(emptyAddress())
      }
    } catch (err) {
      setError(err.message || 'Could not load profile')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  // Map each child to their case services (by matching child_name to full name)
  const childServiceMap = useMemo(() => {
    const map = new Map()
    for (const child of children) {
      const childFull = [child.first_name, child.last_name].filter(Boolean).join(' ').toLowerCase()
      const matched = services.filter(
        (s) => s.child_name?.toLowerCase() === childFull
      )
      map.set(child.id, matched.length ? matched : null)
    }
    return map
  }, [children, services])

  // Patch helper — sends full updated children array
  async function patchChildren(updatedChildren) {
    await apiFetch('/api/v1/parent/profile', {
      method: 'PATCH',
      body: JSON.stringify({
        children: updatedChildren.map((c) => ({
          id: c.id,
          first_name: c.first_name.trim(),
          last_name: (c.last_name || '').trim(),
        })),
      }),
    })
    await loadProfile()
  }

  async function handleEditChildSave(childId, firstName, lastName) {
    const updated = children.map((c) =>
      c.id === childId ? { ...c, first_name: firstName, last_name: lastName } : c,
    )
    await patchChildren(updated)
  }

  async function handleAddChild(nameFull) {
    const { first, last } = splitFullName(nameFull)
    await apiFetch('/api/v1/parent/children', {
      method: 'POST',
      body: JSON.stringify({ first_name: first, last_name: last }),
    })
    await loadProfile()
    setShowAddChild(false)
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const body = {
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        address_type: addressType,
        // Save single address as home_address_* for backward compat
        ...addressToPayload(serviceAddr, 'home_'),
      }
      // Propagate to first homecare case service_address if one exists
      if (homecareCases.length) {
        body.service_address = {
          case_id: Number(homecareCases[0].case_id),
          address: addressToPayload(serviceAddr),
        }
      }
      // Billing address — only save when it's different from service address
      if (!billingSame) {
        Object.assign(body, addressToPayload(billingAddr, 'billing_'))
      }
      await apiFetch('/api/v1/parent/profile', {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      await reloadAuth()
      await loadProfile()
      setSuccess('Profile saved.')
    } catch (err) {
      setError(err.message || 'Could not save profile')
    } finally {
      setSaving(false)
    }
  }

  const layout = (content) => (
    <ClientPortalLayout
      title="My profile"
      subtitle="Update your contact details, children, and visit address. Your care team may have filled in some fields when your case was created."
    >
      {content}
    </ClientPortalLayout>
  )

  if (loading) {
    return layout(<ProfileLoadingSkeleton />)
  }

  return layout(
    <div className="parent-profile">
      <ErrorBanner message={error} onRetry={loadProfile} />
      {success ? <p className="parent-profile__alert parent-profile__alert--success">{success}</p> : null}

      <div className="parent-profile__card parent-profile__avatar-card">
        <AvatarUpload user={user} onUpdated={reloadAuth} size={72} />
      </div>

      <form className="parent-profile__form" onSubmit={handleSave}>
        {/* ── Contact details ── */}
        <section className="parent-profile__card">
          <h3>Your details</h3>
          <p className="parent-profile__hint">How we reach you for appointments and updates.</p>
          <div className="parent-profile__grid">
            <div className="parent-profile__field" style={{ gridColumn: '1 / -1' }}>
              <label>
                Your name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} required autoComplete="name" />
              </label>
            </div>
            <div className="parent-profile__field">
              <label>
                Phone
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="e.g. 98765 43210"
                  autoComplete="tel"
                />
              </label>
            </div>
            <div className="parent-profile__field">
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </label>
            </div>
          </div>
        </section>

        {/* ── Children ── */}
        {children.length > 0 || showAddChild ? (
          <section className="parent-profile__card">
            <div className="parent-profile__card-head">
              <div>
                <h3>{children.length === 1 ? 'Child' : `Children (${children.length})`}</h3>
                <p className="parent-profile__hint" style={{ marginBottom: 0 }}>
                  Names used on reports and session updates. Case reference numbers are shown for each.
                </p>
              </div>
            </div>

            <div className="parent-profile__children-list">
              {children.map((child) => (
                <ChildRow
                  key={child.id}
                  child={child}
                  caseService={childServiceMap.get(child.id)}
                  onEditSave={handleEditChildSave}
                />
              ))}
            </div>

            {showAddChild ? (
              <AddChildForm onAdd={handleAddChild} onCancel={() => setShowAddChild(false)} />
            ) : (
              <button
                type="button"
                className="parent-profile__add-child-btn"
                onClick={() => setShowAddChild(true)}
              >
                + Add another child
              </button>
            )}
          </section>
        ) : (
          <section className="parent-profile__card">
            <div className="parent-profile__card-head">
              <div>
                <h3>Children</h3>
                <p className="parent-profile__hint" style={{ marginBottom: 0 }}>No children on record yet — add one below or contact your care team.</p>
              </div>
            </div>
            {showAddChild ? (
              <AddChildForm onAdd={handleAddChild} onCancel={() => setShowAddChild(false)} />
            ) : (
              <button type="button" className="parent-profile__add-child-btn" onClick={() => setShowAddChild(true)}>
                + Add child
              </button>
            )}
          </section>
        )}

        {/* ── Service address ── */}
        <section className="parent-profile__card">
          <h3>Service address</h3>
          <p className="parent-profile__hint">Where your therapist visits. Use the GPS button to pin the exact location.</p>

          {/* Type: Home / School */}
          <fieldset style={{ border: 'none', padding: 0, margin: '0 0 16px' }}>
            <legend style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Address type
            </legend>
            <div className="parent-profile__address-type">
              {[
                { id: 'home', label: '🏠 Home' },
                { id: 'school', label: '🏫 School' },
              ].map((opt) => (
                <label
                  key={opt.id}
                  className={`parent-profile__address-pill${addressType === opt.id ? ' is-selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="addressType"
                    checked={addressType === opt.id}
                    onChange={() => setAddressType(opt.id)}
                    className="parent-profile__address-pill-input"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>

          <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="service" disabled={saving} />
          {hasCoordinates(serviceAddr) ? (
            <p style={{ fontSize: '0.8rem', color: '#15803d', marginTop: 8 }}>📍 Location pinned on map.</p>
          ) : null}

          {/* Billing address */}
          <div style={{ marginTop: 20, borderTop: '1px solid #f1f5f9', paddingTop: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={billingSame}
                onChange={(e) => setBillingSame(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: '#6366f1', flexShrink: 0 }}
              />
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#0f172a' }}>
                Use this address as billing address
              </span>
            </label>

            {!billingSame ? (
              <div style={{ marginTop: 14 }}>
                <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
                  Billing address
                </p>
                <AddressFormFields value={billingAddr} onChange={setBillingAddr} idPrefix="billing" disabled={saving} />
              </div>
            ) : (
              <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 6 }}>
                Invoices will be addressed to the service address above.
              </p>
            )}
          </div>
        </section>

        <div className="parent-profile__save-bar">
          <button type="submit" className="parent-profile__save" disabled={saving}>
            {saving ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </form>
    </div>,
  )
}

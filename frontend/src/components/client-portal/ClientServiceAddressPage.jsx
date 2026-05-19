import { useEffect, useState } from 'react'
import { AddressFormFields, addressFromApi, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { apiFetch } from '../../lib/apiClient.js'

export function ClientServiceAddressPage({ cases, onSaved }) {
  const homecareCases = cases.filter((c) => c.isHomecare || c.productModule === 'homecare')
  const [selectedId, setSelectedId] = useState(homecareCases[0]?.id ?? '')
  const [addr, setAddr] = useState(emptyAddress())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const selected = homecareCases.find((c) => String(c.id) === String(selectedId))

  useEffect(() => {
    if (homecareCases.length && !selectedId) {
      selectCase(homecareCases[0])
    }
  }, [homecareCases, selectedId])

  function selectCase(c) {
    setSelectedId(c.id)
    setAddr(addressFromApi(c.serviceAddress))
    setError('')
    setSuccess('')
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!selectedId) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/parent/cases/${selectedId}/service-address`, {
        method: 'PATCH',
        body: JSON.stringify(addressToPayload(addr)),
      })
      setSuccess('Service address saved.')
      onSaved?.()
    } catch (err) {
      setError(err.message || 'Could not save address')
    } finally {
      setSaving(false)
    }
  }

  if (!homecareCases.length) {
    return (
      <p className="muted" style={{ fontSize: '0.9rem' }}>
        No homecare cases on your account. Service address is only needed for home visits.
      </p>
    )
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: 16 }}>
        Tell us where homecare sessions should take place. Therapists assigned to your case will see this address.
      </p>

      <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>
        Case
        <select
          className="admin-search__input"
          style={{ width: '100%', marginTop: 4 }}
          value={selectedId}
          onChange={(e) => {
            const c = homecareCases.find((x) => String(x.id) === e.target.value)
            if (c) selectCase(c)
          }}
        >
          {homecareCases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.caseId} · {c.childName}
            </option>
          ))}
        </select>
      </label>

      {selected?.serviceAddressSummary ? (
        <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 12 }}>
          Current: {selected.serviceAddressSummary}
        </p>
      ) : null}

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem' }}>{success}</p> : null}

      <form onSubmit={handleSave} style={{ marginTop: 16 }}>
        <AddressFormFields value={addr} onChange={setAddr} idPrefix="service" disabled={saving} />
        <button
          type="submit"
          disabled={saving}
          style={{
            padding: '10px 20px',
            borderRadius: 8,
            background: '#6366f1',
            color: '#fff',
            fontWeight: 600,
            border: 'none',
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save service address'}
        </button>
      </form>
    </div>
  )
}

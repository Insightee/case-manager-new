import { useEffect, useState } from 'react'
import { AddressFormFields, addressFromApi, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'

function servicePayload(addr) {
  const base = addressToPayload(addr)
  return {
    service_address_line1: base.address_line1,
    service_address_line2: base.address_line2,
    service_city: base.city,
    service_state: base.state,
    service_pincode: base.pincode,
    service_landmark: base.landmark,
    service_latitude: base.latitude,
    service_longitude: base.longitude,
  }
}

export function CaseServiceAddressForm({ caseItem, onSave, readOnly }) {
  const isHomecare =
    caseItem?.product_module === 'homecare' ||
    (caseItem?.service_type || '').toLowerCase().includes('homecare')
  const [addr, setAddr] = useState(emptyAddress())
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (caseItem?.service_address) {
      setAddr(addressFromApi(caseItem.service_address))
    } else {
      setAddr(emptyAddress())
    }
  }, [caseItem])

  if (!isHomecare) return null

  async function handleSubmit(e) {
    e.preventDefault()
    if (readOnly || !onSave) return
    setSaving(true)
    try {
      await onSave(servicePayload(addr))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="admin-form-grid" style={{ maxWidth: 480, marginTop: 16 }} onSubmit={handleSubmit}>
      <p className="admin-drawer__subtitle" style={{ gridColumn: '1 / -1' }}>
        Service address (homecare)
      </p>
      <div style={{ gridColumn: '1 / -1' }}>
        <AddressFormFields value={addr} onChange={setAddr} idPrefix="admin-svc" />
      </div>
      {caseItem?.maps_url ? (
        <p style={{ gridColumn: '1 / -1', fontSize: '0.8rem' }}>
          <a href={caseItem.maps_url} target="_blank" rel="noopener noreferrer">
            Open in Google Maps
          </a>
        </p>
      ) : null}
      {!readOnly && onSave ? (
        <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={saving} style={{ gridColumn: '1 / -1' }}>
          {saving ? 'Saving…' : 'Save service address'}
        </button>
      ) : null}
    </form>
  )
}

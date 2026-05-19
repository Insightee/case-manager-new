import { useState } from 'react'
import { resolveCurrentLocationAddress } from '../../lib/geolocation.js'

const EMPTY = {
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  pincode: '',
  landmark: '',
  latitude: '',
  longitude: '',
}

export function emptyAddress() {
  return { ...EMPTY }
}

export function addressFromApi(addr) {
  if (!addr) return emptyAddress()
  return {
    address_line1: addr.address_line1 || '',
    address_line2: addr.address_line2 || '',
    city: addr.city || '',
    state: addr.state || '',
    landmark: addr.landmark || '',
    pincode: addr.pincode || '',
    latitude: addr.latitude != null ? String(addr.latitude) : '',
    longitude: addr.longitude != null ? String(addr.longitude) : '',
  }
}

export function hasCoordinates(addr) {
  return (
    addr &&
    addr.latitude !== '' &&
    addr.latitude != null &&
    addr.longitude !== '' &&
    addr.longitude != null &&
    !Number.isNaN(Number(addr.latitude)) &&
    !Number.isNaN(Number(addr.longitude))
  )
}

export function addressToPayload(addr, prefix = '') {
  const p = (k) => (prefix ? `${prefix}${k}` : k)
  const body = {}
  if (addr.address_line1) body[p('address_line1')] = addr.address_line1.trim()
  if (addr.address_line2) body[p('address_line2')] = addr.address_line2.trim()
  if (addr.city) body[p('city')] = addr.city.trim()
  if (addr.state) body[p('state')] = addr.state.trim()
  if (addr.pincode) body[p('pincode')] = addr.pincode.trim()
  if (addr.landmark) body[p('landmark')] = addr.landmark.trim()
  if (hasCoordinates(addr)) {
    body[p('latitude')] = Number(addr.latitude)
    body[p('longitude')] = Number(addr.longitude)
  }
  return body
}

const inputStyle = {
  padding: '8px 12px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  fontSize: '0.875rem',
  width: '100%',
}

const labelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  fontSize: '0.875rem',
  fontWeight: 500,
}

export function AddressFormFields({ value, onChange, idPrefix = 'addr', showLocationButton = true, disabled = false }) {
  function setField(key, v) {
    onChange({ ...value, [key]: v })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <label style={labelStyle}>
        Address line 1
        <input
          id={`${idPrefix}-line1`}
          required
          value={value.address_line1}
          onChange={(e) => setField('address_line1', e.target.value)}
          style={inputStyle}
          placeholder="House / building / street"
        />
      </label>
      <label style={labelStyle}>
        Address line 2
        <input
          id={`${idPrefix}-line2`}
          value={value.address_line2}
          onChange={(e) => setField('address_line2', e.target.value)}
          style={inputStyle}
          placeholder="Area, floor (optional)"
        />
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label style={labelStyle}>
          City
          <input
            required
            value={value.city}
            onChange={(e) => setField('city', e.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          State
          <input value={value.state} onChange={(e) => setField('state', e.target.value)} style={inputStyle} />
        </label>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label style={labelStyle}>
          Pincode
          <input
            required
            pattern="[0-9]{6}"
            maxLength={6}
            value={value.pincode}
            onChange={(e) => setField('pincode', e.target.value.replace(/\D/g, '').slice(0, 6))}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Landmark
          <input value={value.landmark} onChange={(e) => setField('landmark', e.target.value)} style={inputStyle} />
        </label>
      </div>

      {showLocationButton ? (
        <UseCurrentLocationButton value={value} onChange={onChange} disabled={disabled} />
      ) : null}

      {hasCoordinates(value) ? (
        <p style={{ fontSize: '0.75rem', color: '#15803d', margin: 0 }}>
          GPS captured: {Number(value.latitude).toFixed(5)}, {Number(value.longitude).toFixed(5)}
        </p>
      ) : null}
    </div>
  )
}

export function UseCurrentLocationButton({ value, onChange, disabled }) {
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState({ type: '', text: '' })

  async function handleClick() {
    setLoading(true)
    setFeedback({ type: '', text: '' })
    try {
      const resolved = await resolveCurrentLocationAddress()
      const next = {
        ...value,
        latitude: String(resolved.latitude),
        longitude: String(resolved.longitude),
      }
      if (resolved.address_line1) next.address_line1 = resolved.address_line1
      if (resolved.address_line2) next.address_line2 = resolved.address_line2
      if (resolved.city) next.city = resolved.city
      if (resolved.state) next.state = resolved.state
      if (resolved.pincode) next.pincode = resolved.pincode
      if (resolved.landmark && !next.landmark) next.landmark = resolved.landmark
      onChange(next)
      setFeedback({
        type: 'ok',
        text: resolved.address_line1
          ? 'Location applied. Review the address fields, then save.'
          : 'GPS coordinates captured. Fill in address fields if needed, then save.',
      })
    } catch (err) {
      setFeedback({ type: 'err', text: err.message || 'Could not get location' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled || loading}
        onClick={handleClick}
        style={{
          padding: '8px 14px',
          borderRadius: 8,
          border: '1px solid #c7d2fe',
          background: loading ? '#e0e7ff' : '#eef2ff',
          color: '#3730a3',
          fontSize: '0.8rem',
          fontWeight: 600,
          cursor: disabled || loading ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        {loading ? 'Getting location…' : 'Use current location'}
      </button>
      {feedback.text ? (
        <p
          style={{
            fontSize: '0.75rem',
            marginTop: 8,
            marginBottom: 0,
            color: feedback.type === 'err' ? '#b91c1c' : '#15803d',
          }}
        >
          {feedback.text}
        </p>
      ) : null}
    </div>
  )
}

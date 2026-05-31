/**
 * Browser geolocation + OpenStreetMap reverse geocoding (no API key).
 * Geolocation requires HTTPS or http://localhost.
 */

import { apiFetch } from './apiClient.js'

function geolocationErrorMessage(error, { manualHint = true } = {}) {
  if (!error) return 'Could not get your location.'
  const suffix = manualHint ? ' You can type the address below — GPS is optional.' : ''
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return `Location permission denied. Allow location for this site in browser settings, then try again.${suffix}`
    case error.POSITION_UNAVAILABLE:
      return `Location unavailable. Check that system location services are on, or enter the address manually.${suffix}`
    case error.TIMEOUT:
      return `Location request timed out. Try again or enter the address manually.${suffix}`
    default:
      return (error.message || 'Could not get your location.') + suffix
  }
}

function requestPosition(options) {
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      reject(new Error('Geolocation is not supported in this browser.'))
      return
    }
    if (typeof window !== 'undefined' && !window.isSecureContext) {
      reject(
        new Error(
          'Location requires a secure page. Open the app via https:// or http://localhost (not a plain IP address).',
        ),
      )
      return
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, options)
  })
}

export function getCurrentPosition(options = {}) {
  const highAccuracy = {
    timeout: 20000,
    maximumAge: 60000,
    ...options,
    enableHighAccuracy: true,
  }
  const lowAccuracy = {
    timeout: 30000,
    maximumAge: 300000,
    ...options,
    enableHighAccuracy: false,
  }

  return requestPosition(highAccuracy).then((pos) => ({
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
  })).catch(async (firstErr) => {
    const POSITION_UNAVAILABLE = 2
    const TIMEOUT = 3
    const retryable = firstErr?.code === POSITION_UNAVAILABLE || firstErr?.code === TIMEOUT
    if (!retryable) {
      throw new Error(geolocationErrorMessage(firstErr))
    }
    try {
      const pos = await requestPosition(lowAccuracy)
      return { latitude: pos.coords.latitude, longitude: pos.coords.longitude }
    } catch (secondErr) {
      throw new Error(geolocationErrorMessage(secondErr))
    }
  })
}

/** @returns {Promise<{ address_line1?: string, address_line2?: string, city?: string, state?: string, pincode?: string, landmark?: string }>} */
export async function reverseGeocode(latitude, longitude) {
  const data = await apiFetch(
    `/api/v1/geocode/reverse?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`,
  )
  return {
    address_line1: data.address_line1 || '',
    address_line2: data.address_line2 || '',
    city: data.city || '',
    state: data.state || '',
    pincode: data.pincode || '',
    landmark: data.landmark || '',
  }
}

export async function resolveCurrentLocationAddress() {
  const coords = await getCurrentPosition()
  let fields = {}
  try {
    fields = await reverseGeocode(coords.latitude, coords.longitude)
  } catch {
    // Coordinates still useful for maps even if reverse geocode fails
  }
  return {
    latitude: coords.latitude,
    longitude: coords.longitude,
    ...fields,
  }
}

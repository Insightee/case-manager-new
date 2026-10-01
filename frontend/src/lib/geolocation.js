/**
 * Browser geolocation + reverse geocoding (no API key).
 * The browser "Allow location" dialog only appears when getCurrentPosition
 * runs in the same user-gesture turn. Do not query permission state first.
 */

import { apiFetch } from './apiClient.js'

export function geolocationErrorMessage(error, { manualHint = true } = {}) {
  if (!error) return 'Could not get your location.'
  const suffix = manualHint ? ' You can type the address below — GPS is optional.' : ''
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return `Location permission denied. Allow location for this site in the browser prompt or site settings, then try again.${suffix}`
    case error.POSITION_UNAVAILABLE:
      return `Location unavailable. Allow this site when the browser asks, and turn on device location services.${suffix}`
    case error.TIMEOUT:
      return `Location request timed out. Try again or enter the address manually.${suffix}`
    default:
      return (error.message || 'Could not get your location.') + suffix
  }
}

const PROMPT_OPTIONS = {
  enableHighAccuracy: true,
  timeout: 25000,
  maximumAge: 0,
}

function coordsFromPosition(pos) {
  return {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
  }
}

/**
 * Ask the browser for location. This is what shows the Allow / Block prompt.
 * Must be called directly from a click — no await before this function starts
 * the getCurrentPosition call.
 */
export function requestBrowserLocation(options = {}) {
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      reject(new Error('Geolocation is not supported in this browser.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(coordsFromPosition(pos)),
      (error) => reject(new Error(geolocationErrorMessage(error))),
      { ...PROMPT_OPTIONS, ...options },
    )
  })
}

export function getCurrentPosition(options = {}) {
  return requestBrowserLocation({
    timeout: 20000,
    ...options,
    enableHighAccuracy: true,
    maximumAge: 0,
  }).catch((firstErr) => {
    const retryable = /unavailable|timed out/i.test(firstErr?.message || '')
    if (!retryable) throw firstErr
    return requestBrowserLocation({
      enableHighAccuracy: false,
      timeout: 30000,
      maximumAge: 0,
      ...options,
    })
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
  const coords = await requestBrowserLocation()
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

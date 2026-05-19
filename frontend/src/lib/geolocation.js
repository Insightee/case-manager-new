/**
 * Browser geolocation + OpenStreetMap reverse geocoding (no API key).
 * Geolocation requires HTTPS or http://localhost.
 */

function geolocationErrorMessage(error) {
  if (!error) return 'Could not get your location.'
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return 'Location permission denied. Allow location for this site in browser settings, then try again.'
    case error.POSITION_UNAVAILABLE:
      return 'Location unavailable. Check that system location services are on.'
    case error.TIMEOUT:
      return 'Location request timed out. Try again or enter the address manually.'
    default:
      return error.message || 'Could not get your location.'
  }
}

export function getCurrentPosition(options = {}) {
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
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => reject(new Error(geolocationErrorMessage(err))),
      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 60000,
        ...options,
      },
    )
  })
}

/** @returns {Promise<{ address_line1?: string, address_line2?: string, city?: string, state?: string, pincode?: string, landmark?: string }>} */
export async function reverseGeocode(latitude, longitude) {
  const url = `/api/v1/geocode/reverse?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`
  const res = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Could not look up address for this location.')
  }
  const data = await res.json()
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

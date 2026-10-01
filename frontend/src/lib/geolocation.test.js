import { describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import { requestBrowserLocation, geolocationErrorMessage } from './geolocation.js'

function stubGeolocation(getCurrentPosition) {
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { geolocation: { getCurrentPosition } },
  })
}

describe('requestBrowserLocation', () => {
  it('calls getCurrentPosition so the browser can show Allow location', async () => {
    const getCurrentPosition = mock.fn((success) => {
      success({ coords: { latitude: 12.97, longitude: 77.59 } })
    })
    stubGeolocation(getCurrentPosition)

    const coords = await requestBrowserLocation()

    assert.equal(getCurrentPosition.mock.calls.length, 1)
    const options = getCurrentPosition.mock.calls[0].arguments[2]
    assert.equal(options.maximumAge, 0)
    assert.equal(options.enableHighAccuracy, true)
    assert.deepEqual(coords, { latitude: 12.97, longitude: 77.59 })
  })

  it('still asks the browser when permission is not already granted', async () => {
    const getCurrentPosition = mock.fn((_success, error) => {
      error({ code: 1, PERMISSION_DENIED: 1, message: 'denied' })
    })
    stubGeolocation(getCurrentPosition)

    await assert.rejects(() => requestBrowserLocation(), /permission denied|Allow location/i)
    assert.equal(getCurrentPosition.mock.calls.length, 1)
  })
})

describe('geolocationErrorMessage', () => {
  it('tells the user to allow the browser prompt', () => {
    const msg = geolocationErrorMessage({ code: 1, PERMISSION_DENIED: 1 })
    assert.match(msg, /Allow location/)
  })
})

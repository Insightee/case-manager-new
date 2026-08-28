import { afterEach, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  FORGOT_PASSWORD_COOLDOWN_KEY,
  FORGOT_PASSWORD_COOLDOWN_SECONDS,
  clearForgotPasswordCooldown,
  readForgotPasswordCooldownRemaining,
  startForgotPasswordCooldown,
} from './forgotPasswordCooldown.js'

const storage = {}
globalThis.sessionStorage = {
  getItem: (key) => storage[key] ?? null,
  setItem: (key, value) => {
    storage[key] = String(value)
  },
  removeItem: (key) => {
    delete storage[key]
  },
  clear: () => {
    for (const key of Object.keys(storage)) delete storage[key]
  },
}

describe('forgotPasswordCooldown', () => {
  afterEach(() => {
    clearForgotPasswordCooldown()
  })

  it('starts and reads a 30 second cooldown window', () => {
    const now = 1_700_000_000_000
    startForgotPasswordCooldown(now)
    assert.equal(
      sessionStorage.getItem(FORGOT_PASSWORD_COOLDOWN_KEY),
      String(now + FORGOT_PASSWORD_COOLDOWN_SECONDS * 1000),
    )
    assert.equal(readForgotPasswordCooldownRemaining(now + 5_000), 25)
  })

  it('clears expired cooldown values', () => {
    const now = 1_700_000_000_000
    startForgotPasswordCooldown(now)
    assert.equal(readForgotPasswordCooldownRemaining(now + 31_000), 0)
    assert.equal(sessionStorage.getItem(FORGOT_PASSWORD_COOLDOWN_KEY), null)
  })
})

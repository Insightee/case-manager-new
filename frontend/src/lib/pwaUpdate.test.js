import assert from 'node:assert/strict'
import test from 'node:test'
import { refreshApp, setPwaUpdateHandler } from './pwaUpdate.js'

test('refreshApp calls injected update(true) then reloads (autoUpdate: update is a no-op)', async () => {
  let called = null
  let reloaded = false
  await refreshApp({
    update: (reloadPage) => {
      called = reloadPage
    },
    reload: () => {
      reloaded = true
    },
  })
  assert.equal(called, true)
  assert.equal(reloaded, true)
})

test('refreshApp reloads when update is missing', async () => {
  let reloaded = false
  await refreshApp({
    update: null,
    reload: () => {
      reloaded = true
    },
  })
  assert.equal(reloaded, true)
})

test('refreshApp reloads when update throws', async () => {
  let reloaded = false
  await refreshApp({
    update: () => {
      throw new Error('sw fail')
    },
    reload: () => {
      reloaded = true
    },
  })
  assert.equal(reloaded, true)
})

test('refreshApp uses registered handler when opts.update is omitted', async () => {
  let called = null
  let reloaded = false
  setPwaUpdateHandler((reloadPage) => {
    called = reloadPage
  })
  await refreshApp({
    reload: () => {
      reloaded = true
    },
  })
  assert.equal(called, true)
  assert.equal(reloaded, true)
  setPwaUpdateHandler(null)
})

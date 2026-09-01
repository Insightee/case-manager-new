import assert from 'node:assert/strict'
import test from 'node:test'
import { refreshApp, setPwaUpdateHandler } from './pwaUpdate.js'

test('refreshApp calls injected update(true) when provided', async () => {
  let called = null
  await refreshApp({
    update: (reloadPage) => {
      called = reloadPage
    },
    reload: () => {
      throw new Error('reload should not run')
    },
  })
  assert.equal(called, true)
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
  setPwaUpdateHandler((reloadPage) => {
    called = reloadPage
  })
  await refreshApp({
    reload: () => {
      throw new Error('reload should not run')
    },
  })
  assert.equal(called, true)
  setPwaUpdateHandler(null)
})

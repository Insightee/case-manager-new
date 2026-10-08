import assert from 'node:assert/strict'
import test from 'node:test'

import {
  __resetInstallPromptStoreForTests,
  getDeferredInstallPrompt,
  initInstallPromptCapture,
  promptDeferredInstall,
  subscribeInstallPrompt,
  wasInstalledThisVisit,
} from './installPromptStore.js'

function makeTarget() {
  const handlers = {}
  return {
    addEventListener: (name, fn) => {
      ;(handlers[name] ||= []).push(fn)
    },
    fire: (name, ev) => (handlers[name] || []).forEach((fn) => fn(ev)),
    count: (name) => (handlers[name] || []).length,
  }
}

test('captures beforeinstallprompt once and prompts only once', async () => {
  __resetInstallPromptStoreForTests()
  const target = makeTarget()
  initInstallPromptCapture(target)
  initInstallPromptCapture(target)
  assert.equal(target.count('beforeinstallprompt'), 1)

  let prevented = false
  let prompted = 0
  let notified = 0
  const unsub = subscribeInstallPrompt(() => notified++)
  target.fire('beforeinstallprompt', {
    preventDefault: () => {
      prevented = true
    },
    prompt: async () => {
      prompted++
    },
    userChoice: Promise.resolve({ outcome: 'accepted' }),
  })
  assert.equal(prevented, true)
  assert.ok(getDeferredInstallPrompt())
  const first = await promptDeferredInstall()
  assert.equal(first.outcome, 'accepted')
  assert.equal(wasInstalledThisVisit(), true)
  assert.equal(getDeferredInstallPrompt(), null)
  const second = await promptDeferredInstall()
  assert.equal(second.outcome, 'unavailable')
  assert.equal(prompted, 1)
  assert.ok(notified >= 2)
  unsub()
})

test('dismissed choice does not mark installed; appinstalled does', async () => {
  __resetInstallPromptStoreForTests()
  const target = makeTarget()
  initInstallPromptCapture(target)
  target.fire('beforeinstallprompt', {
    preventDefault() {},
    prompt: async () => {},
    userChoice: Promise.resolve({ outcome: 'dismissed' }),
  })
  assert.equal((await promptDeferredInstall()).outcome, 'dismissed')
  assert.equal(wasInstalledThisVisit(), false)
  target.fire('appinstalled', {})
  assert.equal(wasInstalledThisVisit(), true)
})

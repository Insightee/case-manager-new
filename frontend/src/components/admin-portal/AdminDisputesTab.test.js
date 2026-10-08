import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const source = readFileSync(path.join(__dirname, 'AdminDisputesTab.jsx'), 'utf8')

describe('AdminDisputesTab', () => {
  it('declares invoice drawer state for row drill-in', () => {
    assert.match(source, /\[drawerId,\s*setDrawerId\]\s*=\s*useState/)
    assert.match(source, /InvoiceDetailDrawer/)
  })
})

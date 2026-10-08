import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const source = readFileSync(path.join(__dirname, 'TherapistIncidentsPage.jsx'), 'utf8')

describe('TherapistIncidentsPage', () => {
  it('unwraps paginated incident lists and surfaces load errors', () => {
    assert.match(source, /import\s*\{[^}]*unwrapList[^}]*\}\s*from\s*['"].*listApi/)
    assert.match(source, /listError/)
    assert.match(source, /setListError/)
  })
})

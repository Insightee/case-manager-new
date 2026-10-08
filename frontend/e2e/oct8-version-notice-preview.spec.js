/**
 * Production preview: build label (iMMDD) + /version.json + update-notice unit contracts (#102).
 */
import { test, expect } from '@playwright/test'
import { execSync, spawn } from 'node:child_process'
import { readFileSync, writeFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loginParent, loginTherapist, loginAdmin } from './helpers/auth.js'
import { ensureArtifactDir, shot } from './helpers/oct8-qa.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '..')
const backendRoot = path.resolve(frontendRoot, '../backend')
const PREVIEW_PORT = 5199
const PREVIEW_URL = `http://127.0.0.1:${PREVIEW_PORT}`
const API_URL = 'http://127.0.0.1:8000'
const EMBEDDED = 'i1006'
const REMOTE = 'i1008'

let previewProc
let backendProc

function patchDistReleaseLabel(distDir, fromLabel, toLabel) {
  const walk = (dir) => {
    for (const name of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, name.name)
      if (name.isDirectory()) walk(full)
      else if (/\.(js|html|css)$/.test(name.name)) {
        let text = readFileSync(full, 'utf8')
        if (text.includes(fromLabel)) {
          writeFileSync(full, text.split(fromLabel).join(toLabel))
        }
      }
    }
  }
  walk(distDir)
}

async function waitForUrl(url, timeoutMs = 120_000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.ok) return
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

test.describe.configure({ mode: 'serial' })
test.use({ baseURL: PREVIEW_URL })

test.beforeAll(async () => {
  backendProc = spawn('bash', ['scripts/e2e-dev-server.sh'], {
    cwd: backendRoot,
    stdio: 'pipe',
    env: {
      ...process.env,
      DATABASE_URL: `sqlite:///${path.join(backendRoot, 'insightcase.version-qa.db')}`,
      RESET_E2E_DB: '1',
      CORS_ORIGINS: `http://127.0.0.1:5173,http://localhost:5173,${PREVIEW_URL}`,
    },
  })
  await waitForUrl(`${API_URL}/health`)

  execSync('npm run build', {
    cwd: frontendRoot,
    stdio: 'inherit',
    env: { ...process.env, VITE_API_URL: API_URL },
  })
  const dist = path.join(frontendRoot, 'dist')
  const manifestPath = path.join(dist, 'version.json')
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  patchDistReleaseLabel(dist, manifest.releaseLabel, EMBEDDED)
  writeFileSync(
    manifestPath,
    `${JSON.stringify({ ...manifest, releaseLabel: REMOTE, buildId: manifest.buildId || 'qa' }, null, 2)}\n`,
  )
  previewProc = spawn('npx', ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PREVIEW_PORT)], {
    cwd: frontendRoot,
    stdio: 'pipe',
    env: { ...process.env, NODE_ENV: 'production' },
  })
  await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('preview timeout')), 120_000)
    previewProc.stdout?.on('data', (d) => {
      if (String(d).includes('Local:')) {
        clearTimeout(t)
        resolve()
      }
    })
    previewProc.stderr?.on('data', () => {})
  })
})

test.afterAll(() => {
  if (previewProc) previewProc.kill('SIGTERM')
  if (backendProc) backendProc.kill('SIGTERM')
})

test('#102 version.json on preview reports newer label', async ({ request }) => {
  const res = await request.get(`${PREVIEW_URL}/version.json`)
  expect(res.ok()).toBeTruthy()
  const body = await res.json()
  expect(body.releaseLabel).toBe(REMOTE)
})

test('#102 update notice unit contracts (appVersionUpdate.test.js)', () => {
  execSync('npm run test:unit -- src/lib/appVersionUpdate.test.js src/lib/releaseLabel.test.js', {
    cwd: frontendRoot,
    stdio: 'inherit',
  })
})

for (const [name, loginFn, pathAfterLogin] of [
  ['parent', loginParent, '/parent'],
  ['therapist', loginTherapist, '/therapist'],
  ['admin', loginAdmin, '/admin'],
]) {
  test(`#102 build label ${EMBEDDED} visible on ${name} preview`, async ({ page }) => {
    await loginFn(page)
    await page.goto(pathAfterLogin)
    await expect(page.getByText(`Build ${EMBEDDED}`).first()).toBeVisible({ timeout: 20_000 })
    ensureArtifactDir()
    await shot(page, `preview-build-label-${name}`)
  })
}

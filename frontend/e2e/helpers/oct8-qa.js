import { execSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(__dirname, '../../../backend')
const e2eDbPath = path.join(backendRoot, 'insightcase.e2e.db')
const e2eDatabaseUrl = process.env.PLAYWRIGHT_DATABASE_URL || `sqlite:///${e2eDbPath}`

export const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
export const ARTIFACT_DIR =
  process.env.OCT8_QA_ARTIFACT_DIR || '/opt/cursor/artifacts/oct8-qa'

export const VIEWPORTS = {
  mobile: { width: 375, height: 812 },
  desktop: { width: 1280, height: 800 },
}

export function ensureArtifactDir() {
  mkdirSync(ARTIFACT_DIR, { recursive: true })
}

/** @param {import('@playwright/test').Page} page @param {string} name */
export async function shot(page, name) {
  ensureArtifactDir()
  const file = path.join(ARTIFACT_DIR, `${name}.png`)
  await page.screenshot({ path: file, fullPage: true })
  return file
}

/** @param {import('@playwright/test').APIRequestContext} request */
export async function apiLogin(request, email, password = 'demo123') {
  const res = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email, password },
  })
  if (!res.ok()) {
    throw new Error(`Login ${email} failed: ${res.status()} ${await res.text()}`)
  }
  const body = await res.json()
  return body.access_token
}

/** @param {string} token */
export function authHeaders(token) {
  return { Authorization: `Bearer ${token}` }
}

/** @param {import('@playwright/test').APIRequestContext} request @param {string} token @param {string} path */
export async function apiGetJson(request, token, path) {
  const res = await request.get(`${API_URL}${path}`, { headers: authHeaders(token) })
  return { status: res.status(), body: res.ok() ? await res.json() : await res.text() }
}

/** @param {import('@playwright/test').APIRequestContext} request @param {string} token */
export async function notificationTitles(request, token, portal = 'staff') {
  const path =
    portal === 'parent' ? '/api/v1/parent/notifications' : '/api/v1/notifications'
  const { status, body } = await apiGetJson(request, token, path)
  if (status !== 200) return []
  const rows = body.notifications ?? body
  return Array.isArray(rows) ? rows.map((r) => r.title) : []
}

export function countTitleDelta(before, after, title) {
  return after.filter((t) => t === title).length - before.filter((t) => t === title).length
}

/** @param {import('@playwright/test').Page} page */
export async function dismissTherapistProfileWelcomeModal(page) {
  const btn = page.getByRole('button', { name: 'Continue to sessions' })
  if (await btn.isVisible({ timeout: 4000 }).catch(() => false)) {
    await btn.click()
  }
}

/** @param {import('@playwright/test').Page} page */
export async function openParentAccountMenu(page) {
  const account = page.getByRole('button', { name: /Account|Profile|Menu/i }).first()
  if (await account.isVisible({ timeout: 3000 }).catch(() => false)) {
    await account.click()
  }
}

/** @param {import('@playwright/test').APIRequestContext} request @param {string} token */
export function runBackendQaScript(scriptName, args = '') {
  return execSync(`python3 scripts/${scriptName} ${args}`.trim(), {
    cwd: backendRoot,
    env: { ...process.env, DATABASE_URL: e2eDatabaseUrl, PYTHONPATH: backendRoot },
    encoding: 'utf8',
  }).trim()
}

/** @param {import('@playwright/test').APIRequestContext} request @param {string} token */
export async function firstCaseId(request, token) {
  const res = await request.get(`${API_URL}/api/v1/cases?page_size=1`, {
    headers: authHeaders(token),
  })
  if (!res.ok()) return null
  const body = await res.json()
  return body.items?.[0]?.id ?? null
}

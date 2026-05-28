import fs from 'fs'
import path from 'path'
import { test, expect } from '@playwright/test'
import { loginTherapist } from './helpers/auth.js'

const DEBUG_LOG = path.resolve(process.cwd(), '../.cursor/debug-3264f0.log')

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

function agentLog(message, data, hypothesisId) {
  const line = JSON.stringify({
    sessionId: '3264f0',
    hypothesisId,
    location: 'report-editor-images.spec.js',
    message,
    data,
    timestamp: Date.now(),
    runId: 'e2e-verify',
  })
  try {
    fs.appendFileSync(DEBUG_LOG, `${line}\n`)
  } catch {
    /* ignore */
  }
}

test.describe('Report editor images', () => {
  test('upload, autosave API paths, reload shows image', async ({ page }) => {
    let patchBody = ''
    page.on('request', (req) => {
      if (req.method() === 'PATCH' && /\/api\/v1\/reports\/monthly\/\d+/.test(req.url())) {
        patchBody = req.postData() || ''
      }
    })

    await loginTherapist(page)
    await page.goto('/therapist/reports')
    await page.getByRole('button', { name: '+ Create Draft' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    const caseSelect = page.getByLabel(/case/i)
    if (await caseSelect.isVisible()) {
      const options = await caseSelect.locator('option').all()
      if (options.length > 1) {
        await caseSelect.selectOption({ index: 1 })
      }
    }
    await page.getByLabel(/month/i).fill('E2E Image Test 2099')
    await page.getByRole('button', { name: /create|save|draft/i }).click()

    await page.waitForURL(/\/therapist\/reports\/edit\/\d+/, { timeout: 15_000 })
    const reportUrl = page.url()
    const reportId = reportUrl.match(/\/edit\/(\d+)/)?.[1]
    agentLog('report_edit_opened', { reportId, reportUrl }, 'H-e2e-flow')

    await expect(page.locator('.report-editor__content')).toBeVisible({ timeout: 15_000 })

    const fileInput = page.locator('.report-editor__file-input')
    await fileInput.setInputFiles({
      name: 'e2e.png',
      mimeType: 'image/png',
      buffer: TINY_PNG,
    })

    const editorImg = page.locator('.report-editor__content img')
    await expect(editorImg).toBeVisible({ timeout: 15_000 })
    const srcAfterUpload = await editorImg.getAttribute('src')
    agentLog('image_after_upload', { srcPrefix: srcAfterUpload?.slice(0, 12) }, 'H-display-blob')

    await page.waitForTimeout(2500)

    expect(patchBody).not.toContain('blob:')
    expect(patchBody).toMatch(/reports\/images\/\d+/)
    agentLog('patch_body_ok', { hasBlob: patchBody.includes('blob:'), hasApiImg: /reports\/images/.test(patchBody) }, 'H-save-api-path')

    await page.reload()
    await expect(page.locator('.report-editor__content')).toBeVisible({ timeout: 15_000 })
    const reloadedImg = page.locator('.report-editor__content img')
    await expect(reloadedImg).toBeVisible({ timeout: 20_000 })
    const naturalWidth = await reloadedImg.evaluate((el) => el.naturalWidth)
    agentLog('image_after_reload', { naturalWidth }, 'H-reload-visible')
    expect(naturalWidth).toBeGreaterThan(0)
  })
})

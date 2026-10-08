import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const artifactsDir = '/opt/cursor/artifacts'

const PRODUCTION_THERAPIST_URL = 'https://www.insighte.org/therapist'

test.describe('App version update notice', () => {
  test.beforeEach(async ({ page, context }, testInfo) => {
    if (!testInfo.project.name.includes('iphone')) {
      await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    }
    await page.addInitScript(() => {
      window.localStorage.setItem('insightcase:version-prior-stale-build', 'i1008')
      if (!navigator.clipboard?.writeText) {
        navigator.clipboard = {
          writeText: async () => {},
        }
      }
    })
    if (testInfo.project.name.includes('desktop')) {
      await page.addInitScript(() => {
        const original = window.matchMedia.bind(window)
        window.matchMedia = (query) => {
          if (query === '(display-mode: standalone)' || query === '(display-mode: fullscreen)') {
            return {
              matches: true,
              media: query,
              addEventListener: () => {},
              removeEventListener: () => {},
              dispatchEvent: () => true,
            }
          }
          return original(query)
        }
      })
    }
  })

  test('primary action opens reinstall sheet with production link', async ({ page }, testInfo) => {
    await page.goto('/e2e/app-version-update')

    await expect(page.getByRole('region', { name: 'App update available' })).toBeVisible()
    await expect(page.getByText("You're on i1006, latest is i1008.")).toBeVisible()
    await expect(page.getByRole('link', { name: PRODUCTION_THERAPIST_URL })).toBeVisible()

    const slug = testInfo.project.name.includes('iphone')
      ? 'iphone'
      : testInfo.project.name.includes('desktop')
        ? 'desktop'
        : 'android'
    await page.screenshot({
      path: path.join(artifactsDir, `app-version-notice-${slug}.png`),
      fullPage: true,
    })

    await page.getByRole('button', { name: 'Re-add shortcut' }).click()

    const sheet = page.getByRole('dialog', { name: /Re-add the InsighteCase shortcut/i })
    await expect(sheet).toBeVisible()
    await expect(sheet.getByRole('link', { name: PRODUCTION_THERAPIST_URL })).toBeVisible()
    if (slug === 'iphone') {
      await expect(sheet.getByRole('button', { name: 'Open in Safari' })).toBeVisible()
      await expect(sheet.getByText(/Add to Home Screen/i)).toBeVisible()
      await expect(sheet.getByText(/chrome:\/\/apps/i)).toHaveCount(0)
    } else if (slug === 'android') {
      await expect(sheet.getByRole('button', { name: 'Open in Chrome' })).toBeVisible()
      await expect(sheet.getByText(/chrome:\/\/apps/i)).toHaveCount(0)
    } else if (slug === 'desktop') {
      await expect(sheet.getByText(/chrome:\/\/apps/i)).toBeVisible()
    }

    await page.screenshot({
      path: path.join(artifactsDir, `app-version-sheet-${slug}.png`),
      fullPage: true,
    })

    await sheet.getByRole('button', { name: 'Copy link' }).first().click()
    await expect(sheet.getByText('Link copied.')).toBeVisible()
  })
})

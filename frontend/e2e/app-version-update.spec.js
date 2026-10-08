import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const artifactsDir = '/opt/cursor/artifacts'

const PRODUCTION_THERAPIST_URL = 'https://www.insighte.org/therapist'

function projectSlug(testInfo) {
  if (testInfo.project.name.includes('iphone')) return 'iphone'
  if (testInfo.project.name.includes('desktop')) return 'desktop'
  return 'android'
}

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

  test('stale notice opens two-step reinstall sheet', async ({ page }, testInfo) => {
    const slug = projectSlug(testInfo)
    await page.goto('/e2e/app-version-update')

    await expect(page.getByRole('region', { name: 'App update available' })).toBeVisible()
    await expect(page.getByText("You're on i1006, latest is i1008.")).toBeVisible()
    await expect(page.getByRole('link', { name: PRODUCTION_THERAPIST_URL })).toBeVisible()

    await page.screenshot({
      path: path.join(artifactsDir, `app-version-notice-${slug}.png`),
      fullPage: true,
    })

    await page.getByRole('button', { name: 'Install InsighteCase' }).click()

    const sheet = page.getByRole('dialog', { name: /Install InsighteCase again/i })
    await expect(sheet).toBeVisible()
    await expect(sheet.locator('.app-version-sheet__step-num').filter({ hasText: '1.' })).toBeVisible()
    await expect(sheet.locator('.app-version-sheet__step-num').filter({ hasText: '2.' })).toBeVisible()

    if (slug === 'iphone') {
      await expect(sheet.getByRole('button', { name: 'Open InsighteCase' })).toBeVisible()
      await expect(sheet.getByText(/Add to Home Screen/i)).toBeVisible()
      await expect(sheet.getByText(/chrome:\/\/apps/i)).toHaveCount(0)
    } else {
      await expect(sheet.getByRole('button', { name: 'Install InsighteCase' })).toBeVisible()
      if (slug === 'desktop') {
        await expect(sheet.getByText(/Uninstall|chrome:\/\/apps/i)).toBeVisible()
      }
    }

    await page.screenshot({
      path: path.join(artifactsDir, `app-version-sheet-${slug}.png`),
      fullPage: true,
    })

    await sheet.getByRole('button', { name: 'Copy link' }).click()
    await expect(sheet.getByText('Link copied.')).toBeVisible()
  })

  test('reinstall=1 landing shows install affordance', async ({ page }, testInfo) => {
    const slug = projectSlug(testInfo)
    const isIphone = slug === 'iphone'

    await page.goto('/e2e/app-version-update?reinstall=1')

    if (!isIphone) {
      await page.evaluate(() => {
        const ev = new Event('beforeinstallprompt', { cancelable: true })
        ev.preventDefault = () => {}
        ev.prompt = async () => {}
        ev.userChoice = Promise.resolve({ outcome: 'accepted' })
        window.dispatchEvent(ev)
      })
    }

    if (isIphone) {
      const landing = page.getByRole('region', { name: /Add InsighteCase to home screen/i })
      await expect(landing).toBeVisible()
      await expect(landing.getByText(/Share → Add to Home Screen/i)).toBeVisible()
    } else {
      const landing = page.getByRole('region', { name: 'Install InsighteCase' })
      await expect(landing).toBeVisible()
      const installBtn = landing.getByRole('button', { name: 'Install InsighteCase' })
      await expect(installBtn).toBeEnabled({ timeout: 10_000 })
    }

    await page.screenshot({
      path: path.join(artifactsDir, `pwa-reinstall-landing-${slug}.png`),
      fullPage: true,
    })
  })
})

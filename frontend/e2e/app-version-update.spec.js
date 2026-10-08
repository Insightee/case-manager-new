import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const shotsDir = process.env.APP_VERSION_SHOTS_DIR || path.join('test-results', 'app-version-shots')
fs.mkdirSync(shotsDir, { recursive: true })

function projectSlug(testInfo) {
  const name = testInfo.project.name
  if (name.includes('iphone')) return 'iphone-375'
  if (name.includes('mac-safari')) return 'mac-safari-1280'
  if (name.includes('desktop-edge')) return 'desktop-edge-1280'
  if (name.includes('desktop')) return 'desktop-chrome-1280'
  return 'android-412'
}

async function shot(page, testInfo, name) {
  await page.screenshot({ path: path.join(shotsDir, `${name}-${projectSlug(testInfo)}.png`), fullPage: true })
}

/** No horizontal scroll at this viewport. */
async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
}

/** Every visible button in scope is at least 44px tall and has an accessible name. */
async function expectTapTargets(scope) {
  const buttons = scope.getByRole('button')
  const count = await buttons.count()
  expect(count).toBeGreaterThan(0)
  for (let i = 0; i < count; i += 1) {
    const button = buttons.nth(i)
    if (!(await button.isVisible())) continue
    const box = await button.boundingBox()
    expect(box.height, `button ${i} height`).toBeGreaterThanOrEqual(44)
    expect(box.width, `button ${i} width`).toBeGreaterThanOrEqual(44)
    expect((await button.textContent())?.trim() || (await button.getAttribute('aria-label'))).toBeTruthy()
  }
}

async function firePrompt(page, outcome = 'accepted') {
  await page.evaluate((choice) => {
    const ev = new Event('beforeinstallprompt', { cancelable: true })
    ev.prompt = async () => {
      window.__promptCalls = (window.__promptCalls || 0) + 1
    }
    ev.userChoice = Promise.resolve({ outcome: choice })
    window.dispatchEvent(ev)
  }, outcome)
}

test.describe('App version update notice + one-tap reinstall', () => {
  test.beforeEach(async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {})
    await page.addInitScript(() => {
      window.localStorage.setItem('insightcase:version-prior-stale-build', 'i1008')
      try {
        if (!navigator.clipboard?.writeText) {
          Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => {} } })
        }
      } catch {
        // ignore
      }
    })
  })

  test('stale notice in the old app has one primary action that opens the browser', async ({ page, context }, testInfo) => {
    const slug = projectSlug(testInfo)
    const iphone = slug.startsWith('iphone')
    const android = slug.startsWith('android')
    await page.goto('/e2e/app-version-update?portal=therapist')

    const notice = page.getByRole('region', { name: 'App update available' })
    await expect(notice).toBeVisible()
    await expect(notice.getByText("You're on i1006, latest is i1008.", { exact: false })).toBeVisible()
    await expect(notice.getByRole('link', { name: /\/therapist$/ })).toBeVisible()
    const primaryName = iphone ? 'Open InsighteCase' : 'Install InsighteCase'
    await expect(notice.locator('.app-version-btn--primary')).toHaveCount(1)
    await expect(notice.getByRole('button', { name: primaryName })).toBeVisible()
    await expect(notice.getByRole('button', { name: 'Copy link' })).toBeVisible()
    await expect(notice.getByRole('button', { name: 'Later' })).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectTapTargets(notice)
    await shot(page, testInfo, '01-stale-notice-in-app')

    // Copy link copies the reinstall URL.
    await notice.getByRole('button', { name: 'Copy link' }).click()
    await expect(notice.getByText('Link copied.')).toBeVisible()

    if (iphone || android) {
      // Scheme handoff (x-safari-https / intent://). Record it instead of leaving the page.
      const handoff = new Promise((resolve) => {
        page.on('request', (req) => {
          const url = req.url()
          if (/^(intent|x-safari-https):/.test(url)) resolve(url)
        })
        page.on('framenavigated', (frame) => {
          const url = frame.url()
          if (/^(intent|x-safari-https):/.test(url)) resolve(url)
        })
      })
      await notice.getByRole('button', { name: primaryName }).click()
      const target = await Promise.race([handoff, page.waitForTimeout(1500).then(() => null)])
      if (target) {
        // Fragments (#Intent;...;end) are not exposed on requests; the full intent is unit-tested.
        if (iphone) expect(target).toMatch(/^x-safari-https:\/\/www\.insighte\.org\/therapist\?reinstall=1$/)
        else expect(target).toMatch(/^intent:\/\/www\.insighte\.org\/therapist\?reinstall=1/)
      }
    } else {
      const popupPromise = context.waitForEvent('page')
      await notice.getByRole('button', { name: primaryName }).click()
      const popup = await popupPromise
      expect(popup.url()).toMatch(/^https:\/\/www\.insighte\.org\/therapist\?reinstall=1$|reinstall=1/)
      await popup.close().catch(() => {})
    }
    if (page.url().includes('/e2e/app-version-update')) {
      await expect(notice.getByText(/If nothing opens, tap Copy link/)).toBeVisible()
      await shot(page, testInfo, '02-stale-notice-after-tap')
    }

    // Later dismisses.
    if (page.url().includes('/e2e/app-version-update')) {
      await notice.getByRole('button', { name: 'Later' }).click()
      await expect(page.getByRole('region', { name: 'App update available' })).toHaveCount(0)
    }
  })

  test('reinstall landing: remove old app first, then one action; no duplicate CTA', async ({ page }, testInfo) => {
    const slug = projectSlug(testInfo)
    const iphone = slug.startsWith('iphone')
    const macSafari = slug.startsWith('mac-safari')
    await page.goto('/e2e/app-version-update?portal=therapist&reinstall=1')

    const dialog = page.getByRole('dialog', { name: 'Install the new InsighteCase' })
    await expect(dialog).toBeVisible()
    // Stale notice is suppressed on the landing: one primary action on screen.
    await expect(page.getByRole('region', { name: 'App update available' })).toHaveCount(0)
    await expect(dialog.getByText('Remove the old app')).toBeVisible()
    // The harness path has no portal segment, so the generic app name is used (portalFromPath is unit-tested).
    await expect(dialog.getByText(/the old InsighteCase/)).toBeVisible()
    await expectNoHorizontalOverflow(page)

    if (iphone) {
      await expect(dialog.getByText(/Share button, then Add to Home Screen, then Add/)).toBeVisible()
      await expect(dialog.getByText(/In Chrome or Edge it is in the address bar/)).toBeVisible()
      await expect(dialog.getByRole('button', { name: 'Install InsighteCase' })).toHaveCount(0)
      await expectTapTargets(dialog)
      await shot(page, testInfo, '03-landing-safari-steps')
    } else if (macSafari) {
      await expect(dialog.getByText(/move the old InsighteCase app to the Trash/)).toBeVisible()
      await expect(dialog.getByText(/choose File, then Add to Dock/)).toBeVisible()
      await expect(dialog.getByRole('button', { name: 'Install InsighteCase' })).toHaveCount(0)
      await expectTapTargets(dialog)
      await shot(page, testInfo, '03-landing-safari-steps')
    } else {
      await expect(dialog.getByRole('button', { name: 'Install InsighteCase' })).toBeDisabled()
      await expect(dialog.getByText('Getting the install ready…')).toBeVisible()
      await shot(page, testInfo, '03-landing-waiting-for-prompt')
      // No prompt after the wait: retry hint with one primary.
      await expect(dialog.getByRole('button', { name: 'Try again' })).toBeVisible({ timeout: 6000 })
      await expect(dialog.getByText(/Make sure the old app is removed \(step 1\)/)).toBeVisible()
      await expect(dialog.locator('.app-version-btn--primary')).toHaveCount(1)
      await expectTapTargets(dialog)
      await shot(page, testInfo, '04-landing-no-prompt-retry')
    }

    // Not now closes and strips ?reinstall=1.
    await dialog.getByRole('button', { name: 'Not now' }).click()
    await expect(page.getByRole('dialog', { name: 'Install the new InsighteCase' })).toHaveCount(0)
    expect(page.url()).not.toContain('reinstall=1')
  })

  test('reinstall landing with browser install prompt: one tap, then success', async ({ page }, testInfo) => {
    const slug = projectSlug(testInfo)
    test.skip(slug.startsWith('iphone') || slug.startsWith('mac-safari'), 'Safari has no install prompt')
    await page.goto('/e2e/app-version-update?portal=therapist&reinstall=1')
    const dialog = page.getByRole('dialog', { name: 'Install the new InsighteCase' })
    await expect(dialog).toBeVisible()
    await firePrompt(page, 'accepted')
    const install = dialog.getByRole('button', { name: 'Install InsighteCase' })
    await expect(install).toBeEnabled()
    await expect(dialog.locator('.app-version-btn--primary')).toHaveCount(1)
    await expectTapTargets(dialog)
    await shot(page, testInfo, '05-landing-install-ready')

    await install.click()
    const done = page.getByRole('dialog', { name: 'You’re all set' })
    await expect(done).toBeVisible()
    const where = slug.startsWith('desktop') ? 'desktop' : 'home screen'
    await expect(done.getByText(`Installed. Open InsighteCase from your ${where}.`)).toBeVisible()
    expect(page.url()).not.toContain('reinstall=1')
    expect(await page.evaluate(() => window.__promptCalls)).toBe(1)
    await expectNoHorizontalOverflow(page)
    await shot(page, testInfo, '06-landing-installed')
    await done.getByRole('button', { name: 'Done' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('cancelled install prompt offers Try again', async ({ page }, testInfo) => {
    test.skip(/^(iphone|mac-safari)/.test(projectSlug(testInfo)), 'Safari has no install prompt')
    await page.goto('/e2e/app-version-update?portal=therapist&reinstall=1')
    const dialog = page.getByRole('dialog', { name: 'Install the new InsighteCase' })
    await firePrompt(page, 'dismissed')
    await dialog.getByRole('button', { name: 'Install InsighteCase' }).click()
    await expect(dialog.getByText('Install was cancelled. Tap Try again when you are ready.')).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Try again' })).toBeVisible()
  })

  test('landing survives a login redirect that drops the query', async ({ page }) => {
    await page.goto('/e2e/app-version-update?portal=parent&reinstall=1')
    await expect(page.getByRole('dialog', { name: 'Install the new InsighteCase' })).toBeVisible()
    // Simulate a redirect that loses ?reinstall=1 in the same tab.
    await page.evaluate(() => window.history.replaceState(null, '', '/e2e/app-version-update?portal=parent'))
    await page.reload()
    const dialog = page.getByRole('dialog', { name: 'Install the new InsighteCase' })
    await expect(dialog).toBeVisible()
    expect(page.url()).not.toContain('reinstall=1')
  })

  for (const portal of ['parent', 'admin']) {
    test(`${portal} portal: same notice and landing`, async ({ page }, testInfo) => {
      const slug = projectSlug(testInfo)
      await page.goto(`/e2e/app-version-update?portal=${portal}`)
      const notice = page.getByRole('region', { name: 'App update available' })
      await expect(notice.getByRole('link', { name: new RegExp(`/${portal}$`) })).toBeVisible()
      await expect(notice.locator('.app-version-btn--primary')).toHaveCount(1)
      await expectNoHorizontalOverflow(page)
      await shot(page, testInfo, `07-${portal}-stale-notice`)
      await page.goto(`/e2e/app-version-update?portal=${portal}&reinstall=1`)
      const dialog = page.getByRole('dialog', { name: 'Install the new InsighteCase' })
      await expect(dialog.getByText('Remove the old app')).toBeVisible()
      if (!/^(iphone|mac-safari)/.test(slug)) await firePrompt(page)
      await expectNoHorizontalOverflow(page)
      await shot(page, testInfo, `08-${portal}-landing`)
    })
  }
})

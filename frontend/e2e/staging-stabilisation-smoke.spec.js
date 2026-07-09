import { test, expect } from '@playwright/test'
import { loginTherapist, navigateTherapist } from './helpers/auth.js'
import { openCaseLogsTab } from './helpers/caseNav.js'

test.describe('Staging stabilisation smoke (mobile)', () => {
  test.use({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  })

  test('therapist case navigation and session logs on mobile', async ({ page }) => {
    await loginTherapist(page)

    await navigateTherapist(page, 'My Cases')
    await expect(page).toHaveURL(/\/therapist\/cases/)
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()

    const caseLink = page.getByRole('link', { name: 'Open case file' }).first()
    await expect(caseLink).toBeVisible()
    await caseLink.click()
    await expect(page).toHaveURL(/\/therapist\/cases\/\d+/)

    await openCaseLogsTab(page)
  })

  test('monthly reports page loads on mobile', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Reports')
    await expect(page).toHaveURL(/\/therapist\/reports/)
    await expect(page.getByRole('heading', { name: /Reports Dashboard|Reports ·/i })).toBeVisible()
    await expect(page.getByRole('group', { name: 'Reports summary' })).toBeVisible()
  })
})

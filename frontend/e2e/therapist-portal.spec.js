import { test, expect } from '@playwright/test'
import { loginTherapist, navigateTherapist, sidebarLink } from './helpers/auth.js'
import { expectCaseOverviewLoaded, openCaseLogsTab } from './helpers/caseNav.js'

test.describe('Therapist portal smoke', () => {
  test('dashboard, navigation, and core pages load with API data', async ({ page }) => {
    await loginTherapist(page)

    await expect(page.getByRole('heading', { level: 2 })).toBeVisible()
    await expect(page.locator('#td-schedule-title, .td-schedule').first()).toBeVisible()

    await sidebarLink(page, 'Session Logs').click()
    await expect(page).toHaveURL(/\/therapist\/logs/)
    await expect(page.getByRole('heading', { name: 'Session Logs' })).toBeVisible()
    await expect(page.getByRole('tablist', { name: 'Session log lists' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Start now' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Forgot to log' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Child absence' })).toBeVisible()
    await page.getByRole('tab', { name: 'Forgot to log' }).click()
    await expect(page.getByRole('heading', { name: 'Log a session you missed' })).toBeVisible()
    await expect(page.getByLabel('Session date')).toBeVisible()
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('region', { name: 'Add or start session' })).toBeVisible()
    await page.getByRole('tab', { name: 'Approved' }).click()
    const viewBtn = page.getByRole('button', { name: 'View log' }).first()
    if (await viewBtn.isVisible()) {
      await viewBtn.click()
      await expect(page.getByText(/cannot be edited/i)).toBeVisible()
    }

    await sidebarLink(page, 'My Cases').click()
    await expect(page).toHaveURL(/\/therapist\/cases/)
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    await expect(page.getByRole('tablist', { name: 'Filter by status' })).toBeVisible()

    await sidebarLink(page, 'Reports').click()
    await expect(page).toHaveURL(/\/therapist\/reports/)
    await expect(page.getByRole('heading', { name: /Reports Dashboard|Reports ·/i })).toBeVisible()
    await expect(page.getByRole('group', { name: 'Reports summary' })).toBeVisible()

    await sidebarLink(page, 'Invoices').click()
    await expect(page).toHaveURL(/\/therapist\/invoices/)
    await expect(page.getByRole('heading', { name: 'Invoices', exact: true })).toBeVisible()
  })

  test('my cases detail opens from board', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'My Cases').click()
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()

    const caseLink = page.getByRole('link', { name: 'Open case file' }).first()
    await expect(caseLink).toBeVisible()
    await caseLink.click()
    await expect(page).toHaveURL(/\/therapist\/cases\/\d+/)
    await expectCaseOverviewLoaded(page)

    await openCaseLogsTab(page)

    await page.goBack()
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    const logChip = page.getByRole('link', { name: /log/i }).first()
    if (await logChip.isVisible()) {
      await logChip.click()
      await expect(page).toHaveURL(/\/therapist\/(cases\/\d+|logs)/)
    }
  })

  test('session log flow: start, end, and submit form', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'Session Logs').click()

    const startBtn = page.getByRole('button', { name: 'Start session' }).first()
    if (await startBtn.isVisible()) {
      await startBtn.click()
      await expect(page.getByRole('heading', { name: 'Session in Progress' })).toBeVisible({ timeout: 15_000 })
      await expect(page.getByRole('region', { name: 'Session in progress' })).toBeVisible()
      await page.getByRole('button', { name: /End Session/i }).click()
      await expect(page.getByText(/Complete Session Log/i)).toBeVisible({ timeout: 15_000 })
      await page.getByLabel('Attendance').selectOption('PRESENT')
      await page.getByLabel('Session notes (internal)').fill('Playwright E2E session notes')
      await page.getByLabel('Activities').fill('Play activities')
      await page.getByLabel('Goals worked on').fill('Communication goals')
      await page.getByLabel('Observations (internal)').fill('Engaged throughout')
      await page.getByLabel('Follow-ups').fill('Continue plan')
      await page.getByLabel('Notes for family').fill('Good session today')
      await page.getByRole('button', { name: /Submit log/i }).click()
      await expect(page.getByText(/submitted for review/i)).toBeVisible({ timeout: 15_000 })
    } else {
      const needsLog = page.getByRole('button', { name: /needs log/i }).first()
      if (await needsLog.isVisible()) {
        await needsLog.click()
        await expect(page.getByText(/Complete session log/i)).toBeVisible()
      } else {
        test.skip(true, 'No startable session or pending log in seed data')
      }
    }
  })

  test('my cases status filter pills work', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'My Cases').click()
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Your case cards' })).toBeVisible()
    await page.getByRole('tab', { name: 'Active' }).click()
    await expect(page.getByRole('tab', { name: 'Active', selected: true })).toBeVisible()
    await page.getByRole('tab', { name: 'All' }).click()
    await expect(page.getByRole('tab', { name: 'All', selected: true })).toBeVisible()
  })

  test('monthly report draft modal opens', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'Reports').click()
    await page.getByRole('button', { name: '+ Create New Draft' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('heading', { name: /new monthly report draft/i })).toBeVisible()
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()
  })
})

test.describe('Therapist portal mobile', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('session composer and case tabs on narrow viewport', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Session Logs')
    await expect(page.getByRole('tab', { name: 'Start now' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Forgot to log' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Child absence' })).toBeVisible()
    await page.getByRole('tab', { name: 'Forgot to log' }).click()
    await expect(page.getByRole('heading', { name: 'Log a session you missed' })).toBeVisible()
    await expect(page.getByLabel('Session date')).toBeVisible()
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('region', { name: 'Add or start session' })).toBeVisible()

    await navigateTherapist(page, 'My Cases')
    const caseLink = page.getByRole('link', { name: 'Open case file' }).first()
    await caseLink.click()
    await expect(page.getByRole('navigation', { name: 'Case sections' })).toBeVisible()
    await openCaseLogsTab(page)
  })

  test('leave request form opens on mobile', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Leave')
    await expect(page.getByRole('heading', { name: 'My Leave' })).toBeVisible()
    await page.getByRole('button', { name: '+ Request leave' }).click()
    await expect(page.getByText('New leave request')).toBeVisible()
    await expect(page.getByLabel('From date')).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
  })

  test('my cases filter pills visible on mobile', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'My Cases')
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    await expect(page.getByRole('tablist', { name: 'Filter by status' })).toBeVisible()
    await expect(page.getByLabel('Search cases')).toBeVisible()
  })

  test('drawer nav omits duplicate My Profile link', async ({ page }) => {
    await loginTherapist(page)
    await page.getByRole('button', { name: /Open navigation menu/i }).click()
    const drawerNav = page.locator('#portal-nav-drawer .app-sidebar__nav')
    await expect(drawerNav.getByRole('link', { name: 'My Profile' })).toHaveCount(0)
    await expect(page.locator('#portal-nav-drawer').getByRole('link', { name: 'My profile' })).toBeVisible()
  })

  test('open slots page fits viewport without horizontal scroll', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Scheduling')
    await expect(page.getByRole('heading', { name: 'Scheduling' })).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
  })
})

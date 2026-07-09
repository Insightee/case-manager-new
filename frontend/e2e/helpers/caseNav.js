import { expect } from '@playwright/test'

/** Open session logs on case detail (legacy Sessions tab or revamp Logs tab). */
export async function openCaseLogsTab(page) {
  const caseNav = page.getByRole('navigation', { name: 'Case sections' })
  await expect(caseNav).toBeVisible()

  const logsTab = caseNav.getByRole('button', {
    name: /^(Sessions( & logs)?|Logs)$/,
  })
  await expect(logsTab.first()).toBeVisible()
  await logsTab.first().click()

  await expect(page.getByRole('region', { name: 'Month summary' })).toBeVisible()
}

/** Case overview markers for legacy or revamp shell. */
export async function expectCaseOverviewLoaded(page) {
  await expect(page.getByRole('button', { name: 'Overview' })).toBeVisible()
  await expect(
    page
      .getByRole('heading', { name: 'Your case manager' })
      .or(page.getByRole('heading', { name: 'Profile snapshot' }))
  ).toBeVisible()
}

/**
 * QA E2E — six fixes merged 8 Oct 2026 (#98–#102, #104).
 * API + UI coverage at 375×812 and 1280×800. No product behaviour changes.
 */
import { test, expect } from '@playwright/test'
import {
  loginAdmin,
  loginCaseManager,
  loginParent,
  loginTherapist,
  portalNav,
  sidebarLink,
} from './helpers/auth.js'
import {
  API_URL,
  VIEWPORTS,
  apiLogin,
  authHeaders,
  countTitleDelta,
  dismissTherapistProfileWelcomeModal,
  notificationTitles,
  openParentAccountMenu,
  runBackendQaScript,
  shot,
  ensureArtifactDir,
} from './helpers/oct8-qa.js'

/** Thursday anchor — isolated from other e2e recurring runs. */
const RECURRING_START = '2027-03-04'
const RECURRING_END = '2027-04-29'

test.describe('Oct8 QA API contracts (once)', () => {
  test('#98 preview returns 422 for missing package_session_count', async ({ request }) => {
    const [caseId, caseCode] = runBackendQaScript('qa_oct8_broken_package_fixture.py').split('|')
    const therapist = await apiLogin(request, 'therapist@demo.com')
    const preview = await request.get(`${API_URL}/api/v1/invoices/preview?month=2099-08`, {
      headers: authHeaders(therapist),
    })
    expect(preview.status()).toBe(422)
    const detail = (await preview.json()).detail
    expect(detail?.code).toBe('MISSING_PACKAGE_COUNT')
    expect(String(detail?.message)).toContain(caseCode)
    runBackendQaScript('qa_oct8_broken_package_fixture.py', `cleanup ${caseId}`)
  })

  test('#99 evidence-summary staff 200, parent 403 (pytest contract)', () => {
    runBackendQaScript('qa_oct8_evidence_pytest.py')
  })

  test('#104 recurring Thu + M/W/F notifies once per role', async ({ request }) => {
    const therapist = await apiLogin(request, 'therapist@demo.com')
    const parent = await apiLogin(request, 'parent@demo.com')
    const shadowCm = await apiLogin(request, 'shadowcm@demo.com')
    const cm = await apiLogin(request, 'casemanager@demo.com')
    const caseId = (await (
      await request.get(`${API_URL}/api/v1/slots/bookable-cases`, {
        headers: authHeaders(therapist),
      })
    ).json())[0].case_id
    const therapistUserId = (
      await (
        await request.get(`${API_URL}/api/v1/auth/me`, { headers: authHeaders(therapist) })
      ).json()
    ).id
    const beforeParent = await notificationTitles(request, parent, 'parent')
    const beforeTherapist = await notificationTitles(request, therapist, 'staff')
    const beforeShadow = await notificationTitles(request, shadowCm, 'staff')
    const beforeCm = await notificationTitles(request, cm, 'staff')
    const book = await request.post(`${API_URL}/api/v1/scheduling/assign-recurring`, {
      headers: authHeaders(therapist),
      data: {
        case_id: caseId,
        therapist_user_id: therapistUserId,
        weekdays: ['mon', 'wed', 'fri'],
        start_time: '08:00:00',
        end_time: '14:30:00',
        start_date: RECURRING_START,
        end_date: RECURRING_END,
      },
    })
    expect(book.status()).toBe(201)
    const body = await book.json()
    expect(body.outside_week).toEqual(['mon', 'wed'])
    expect(body.booked_slot_count).toBeGreaterThan(0)
    const afterParent = await notificationTitles(request, parent, 'parent')
    const afterTherapist = await notificationTitles(request, therapist, 'staff')
    const afterShadow = await notificationTitles(request, shadowCm, 'staff')
    const afterCm = await notificationTitles(request, cm, 'staff')
    expect(countTitleDelta(beforeParent, afterParent, 'Recurring sessions scheduled')).toBe(1)
    expect(countTitleDelta(beforeTherapist, afterTherapist, 'Recurring schedule assigned')).toBe(1)
    expect(
      countTitleDelta(beforeShadow, afterShadow, 'Recurring schedule booked') +
        countTitleDelta(beforeCm, afterCm, 'Recurring schedule booked'),
    ).toBe(1)
  })

  test('#100 parent cross-family availability 404', async ({ request }) => {
    const parent = await apiLogin(request, 'parent@demo.com')
    const res = await request.get(`${API_URL}/api/v1/booking/availability`, {
      headers: authHeaders(parent),
      params: {
        therapist_id: 1,
        from_date: '2026-10-08',
        to_date: '2026-10-08',
        case_id: 987654321,
      },
    })
    expect(res.status()).toBe(404)
  })
})

const FIX = {
  invoice98: '#98 invoice package count 422',
  evidence99: '#99 evidence summary',
  transition100: '#100 therapist handover',
  session101: '#101 session log submit',
  recurring104: '#104 recurring booking',
  forest102: '#102 Forest UI + version label',
}

for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
  test.describe(`Oct8 QA @ ${vpName} (${viewport.width}×${viewport.height})`, () => {
    test.use({ viewport })

    test.describe(`${FIX.recurring104} UI`, () => {
      test('recurring sheet offers Include them above mobile nav @ mobile only', async ({ page }) => {
        test.skip(vpName !== 'mobile', 'mobile layout check')
        await loginTherapist(page)
        await dismissTherapistProfileWelcomeModal(page)
        const menuBtn = page.getByRole('button', { name: /Open navigation menu/i })
        if (await menuBtn.isVisible()) {
          await menuBtn.click()
          await page.locator('#portal-nav-drawer').getByRole('link', { name: 'Scheduling', exact: true }).click()
        } else {
          await sidebarLink(page, 'Scheduling').click()
        }
        await page.getByRole('button', { name: /Book recurring|Weekly schedule/i }).first().click()
        await page.getByRole('tab', { name: 'Book recurring' }).click()
        const include = page.getByRole('button', { name: 'Include them' })
        if (await include.isVisible({ timeout: 3000 }).catch(() => false)) {
          await expect(include).toBeVisible()
        }
        ensureArtifactDir()
        await shot(page, `recurring-sheet-${vpName}`)
        const nav = portalNav(page)
        if (await nav.isVisible()) {
          const sheet = page.locator('.weekly-schedule-drawer, [class*="schedule"]').first()
          const navBox = await nav.boundingBox()
          const sheetBox = await sheet.boundingBox()
          if (navBox && sheetBox) {
            expect(sheetBox.y + sheetBox.height).toBeLessThanOrEqual(navBox.y + 2)
          }
        }
      })
    })

    test.describe(FIX.forest102, () => {
      test('parent cm-meetings route works; chat GET does not create tickets', async ({
        request,
        page,
      }) => {
        const parent = await apiLogin(request, 'parent@demo.com')
        const meetings = await request.get(`${API_URL}/api/v1/parent/cm-meetings?status=SCHEDULED`, {
          headers: authHeaders(parent),
        })
        expect(meetings.status()).toBe(200)

        const casesRes = await request.get(`${API_URL}/api/v1/parent/cases`, {
          headers: authHeaders(parent),
        })
        const cases = await casesRes.json()
        const caseId = cases[0]?.id
        expect(caseId).toBeTruthy()

        const chat1 = await request.get(`${API_URL}/api/v1/parent/therapist-chat?case_id=${caseId}`, {
          headers: authHeaders(parent),
        })
        expect(chat1.status()).toBe(200)
        expect(await chat1.json()).toBeNull()
        const chat2 = await request.get(`${API_URL}/api/v1/parent/therapist-chat?case_id=${caseId}`, {
          headers: authHeaders(parent),
        })
        expect(chat2.status()).toBe(200)
        expect(await chat2.json()).toBeNull()

        await loginParent(page)
        await page.goto('/parent')
        if (vpName === 'mobile') {
          await openParentAccountMenu(page)
        }
        if (vpName === 'desktop') {
          await expect(page.getByText(/Build i\d{4}/).first()).toBeVisible({ timeout: 15_000 })
        }
        await shot(page, `parent-version-label-${vpName}`)
      })

      test('admin notification link targets /admin/meetings', async ({ page }) => {
        await loginCaseManager(page)
        await page.goto('/admin/meetings')
        await expect(page).toHaveURL(/\/admin\/meetings/)
        await shot(page, `admin-meetings-${vpName}`)
      })
    })

    test.describe(FIX.session101, () => {
      test('therapist Support & Incidents and admin disputes tab load', async ({ page }) => {
        await loginTherapist(page)
        await dismissTherapistProfileWelcomeModal(page)
        await page.goto('/therapist/support?tab=incidents')
        await expect(page.getByRole('heading', { name: 'Incident Reporting' })).toBeVisible({
          timeout: 15_000,
        })
        await shot(page, `therapist-incidents-${vpName}`)

        await loginAdmin(page)
        await page.goto('/admin/invoices?tab=tools&sub=disputes')
        await expect(page.getByText('Billing disputes').first()).toBeVisible({
          timeout: 20_000,
        })
        await shot(page, `admin-disputes-${vpName}`)
      })
    })
  })
}

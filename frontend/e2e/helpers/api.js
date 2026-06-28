/** @param {import('@playwright/test').APIRequestContext} request */
export async function therapistApiToken(request, apiURL = 'http://127.0.0.1:8000') {
  const login = await request.post(`${apiURL}/api/v1/auth/login`, {
    data: { email: 'therapist@demo.com', password: 'demo123' },
  })
  if (!login.ok()) {
    throw new Error(`Therapist login failed: ${login.status()} ${await login.text()}`)
  }
  const body = await login.json()
  return body.access_token
}

/** @param {import('@playwright/test').APIRequestContext} request */
export async function findTodayScheduledSessionId(request, token, apiURL = 'http://127.0.0.1:8000') {
  const headers = { Authorization: `Bearer ${token}` }
  const res = await request.get(`${apiURL}/api/v1/therapist/sessions/workspace`, { headers })
  if (!res.ok()) return null
  const body = await res.json()
  const upcoming = body.upcoming || []
  const scheduled = upcoming.filter((s) => s.status === 'SCHEDULED')
  if (!scheduled.length) return null
  const today = new Date().toISOString().slice(0, 10)
  return scheduled.find((s) => s.scheduled_date === today)?.id ?? scheduled[0]?.id ?? null
}

/** Pick a client in the absence composer that has a visit today (if any). */
export async function openChildAbsenceForm(page) {
  await page.getByRole('tab', { name: 'Child absence' }).click()
  const clientSelect = page.getByRole('combobox', { name: 'Client' })
  if (!(await clientSelect.isVisible())) return false
  const options = await clientSelect.locator('option').allTextContents()
  for (let i = 1; i < options.length; i += 1) {
    await clientSelect.selectOption({ index: i })
    const submit = page.getByRole('button', { name: /Log child absent/i })
    if (await submit.isVisible({ timeout: 500 }).catch(() => false)) {
      return true
    }
  }
  return false
}

/** @param {import('@playwright/test').APIRequestContext} request */
export async function findNeedsLogSessionId(request, token, apiURL = 'http://127.0.0.1:8000') {
  const headers = { Authorization: `Bearer ${token}` }
  const res = await request.get(`${apiURL}/api/v1/therapist/sessions/workspace`, { headers })
  if (!res.ok()) return null
  const body = await res.json()
  return body.needs_log?.[0]?.id ?? null
}

/** End active sessions, then start+end a scheduled visit so it lands in Needs log. */
export async function ensureNeedsLogSession(request, token, apiURL = 'http://127.0.0.1:8000') {
  const headers = { Authorization: `Bearer ${token}` }
  await endInProgressSessions(request, token, apiURL)

  let needsId = await findNeedsLogSessionId(request, token, apiURL)
  if (needsId) return needsId

  const sessionId = await findTodayScheduledSessionId(request, token, apiURL)
  if (!sessionId) return null

  const start = await request.post(`${apiURL}/api/v1/sessions/${sessionId}/start`, { headers, data: {} })
  if (!start.ok()) return null
  const end = await request.post(`${apiURL}/api/v1/sessions/${sessionId}/end`, { headers, data: {} })
  if (!end.ok()) return null

  return findNeedsLogSessionId(request, token, apiURL)
}

/** @param {import('@playwright/test').APIRequestContext} request */
export async function endInProgressSessions(request, token, apiURL = 'http://127.0.0.1:8000') {
  const headers = { Authorization: `Bearer ${token}` }
  const ws = await request.get(`${apiURL}/api/v1/therapist/sessions/workspace`, { headers })
  if (!ws.ok()) return
  const body = await ws.json()
  const active = body.active_session
  if (!active?.id) return
  const cancel = await request.post(`${apiURL}/api/v1/sessions/${active.id}/cancel`, { headers, data: {} })
  if (!cancel.ok()) {
    await request.post(`${apiURL}/api/v1/sessions/${active.id}/end`, { headers, data: {} })
  }
}

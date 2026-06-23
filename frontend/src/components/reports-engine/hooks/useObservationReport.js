import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

const AUTO_SAVE_MS = 5 * 60 * 1000

export function useObservationReport(caseId) {
  const [summary, setSummary] = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [preview, setPreview] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [candidates, setCandidates] = useState({ goals: [], strategies: [] })
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)

  useEffect(() => {
    savingRef.current = saving
  }, [saving])

  const loadSummary = useCallback(async () => {
    if (!caseId) return null
    const data = await apiFetch(`/api/v1/cases/${caseId}/reports/observation/summary`)
    setSummary(data)
    return data
  }, [caseId])

  const loadWorkspace = useCallback(async () => {
    if (!caseId) return null
    const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/observation`)
    setWorkspace(ws)
    if (ws.report_id) {
      const [ev, cand] = await Promise.all([
        apiFetch(`/api/v1/reports/${ws.report_id}/evidence-summary`).catch(() => null),
        apiFetch(`/api/v1/reports/${ws.report_id}/observation/candidates`).catch(() => ({ goals: [], strategies: [] })),
      ])
      setEvidence(ev)
      setCandidates(cand)
      const clinical = ws.sections?.find((s) => s.key === 'clinical_summary')
      if (clinical?.structured_data?.session_insights) {
        setInsights(clinical.structured_data.session_insights)
      }
    }
    return ws
  }, [caseId])

  const loadPreview = useCallback(async (reportId) => {
    const id = reportId || workspace?.report_id || summary?.report_id
    if (!id) return null
    const data = await apiFetch(`/api/v1/reports/${id}/preview`)
    setPreview(data)
    return data
  }, [workspace?.report_id, summary?.report_id])

  const refresh = useCallback(async (mode = 'summary') => {
    if (!caseId) return
    setLoading(true)
    setError('')
    try {
      if (mode === 'summary') await loadSummary()
      else if (mode === 'workspace') await loadWorkspace()
      else if (mode === 'preview') await loadPreview()
    } catch (err) {
      setError(err.message || 'Could not load observation report')
    } finally {
      setLoading(false)
    }
  }, [caseId, loadSummary, loadWorkspace, loadPreview])

  useEffect(() => {
    refresh('summary')
  }, [refresh])

  async function startReport() {
    setSaving(true)
    setError('')
    try {
      const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/observation/start`, { method: 'POST' })
      setWorkspace(ws)
      await loadSummary()
      return ws
    } catch (err) {
      setError(err.message || 'Could not start observation report')
      throw err
    } finally {
      setSaving(false)
    }
  }

  async function patchSection(sectionKey, patch) {
    if (!workspace?.report_id) return
    setSaving(true)
    setError('')
    try {
      await apiFetch(`/api/v1/reports/${workspace.report_id}/sections/${sectionKey}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      await loadWorkspace()
      await loadSummary()
    } catch (err) {
      setError(err.message || 'Could not save this section')
    } finally {
      setSaving(false)
    }
  }

  async function submitReport() {
    if (!workspace?.report_id) return
    setSaving(true)
    setError('')
    try {
      await apiFetch(`/api/v1/reports/${workspace.report_id}/submit`, { method: 'POST' })
      await loadWorkspace()
      await loadSummary()
    } catch (err) {
      setError(err.message || 'Could not submit for review')
    } finally {
      setSaving(false)
    }
  }

  async function generateInsights() {
    if (!workspace?.report_id) return
    setSaving(true)
    try {
      const data = await apiFetch(`/api/v1/reports/${workspace.report_id}/observation/generate-insights`, {
        method: 'POST',
      })
      setInsights(data)
      await loadWorkspace()
    } catch (err) {
      setError(err.message || 'Could not generate session insights')
    } finally {
      setSaving(false)
    }
  }

  async function addGoalCandidate(label, domainKey = 'general') {
    if (!workspace?.report_id || !label.trim()) return
    await apiFetch(`/api/v1/reports/${workspace.report_id}/observation/goal-candidates`, {
      method: 'POST',
      body: JSON.stringify({ label: label.trim(), domain_key: domainKey }),
    })
    await loadWorkspace()
    const cand = await apiFetch(`/api/v1/reports/${workspace.report_id}/observation/candidates`).catch(() => ({ goals: [], strategies: [] }))
    setCandidates(cand)
  }

  async function addStrategyCandidate(label, description = '') {
    if (!workspace?.report_id || !label.trim()) return
    await apiFetch(`/api/v1/reports/${workspace.report_id}/observation/strategy-candidates`, {
      method: 'POST',
      body: JSON.stringify({ label: label.trim(), description }),
    })
    await loadWorkspace()
  }

  async function searchStrategies(q) {
    if (!workspace?.report_id || !q.trim()) return []
    const data = await apiFetch(
      `/api/v1/reports/${workspace.report_id}/observation/strategy-matches?q=${encodeURIComponent(q)}`,
    )
    return data.items || []
  }

  const waitForSavingIdle = useCallback(async () => {
    let attempts = 0
    while (savingRef.current && attempts < 60) {
      await new Promise((resolve) => { setTimeout(resolve, 50) })
      attempts += 1
    }
  }, [])

  const saveDraft = useCallback(async (flushPending) => {
    if (!workspace?.report_id) return null
    setSaving(true)
    setError('')
    try {
      if (typeof flushPending === 'function') {
        flushPending()
      }
      await waitForSavingIdle()
      const ws = await apiFetch(`/api/v1/reports/${workspace.report_id}/save-draft`, { method: 'POST' })
      setWorkspace(ws)
      await loadSummary()
      return ws
    } catch (err) {
      setError(err.message || 'Could not save draft')
      return null
    } finally {
      setSaving(false)
    }
  }, [workspace?.report_id, waitForSavingIdle, loadSummary])

  async function applyInsights() {
    if (!workspace?.report_id) return null
    setSaving(true)
    try {
      const data = await apiFetch(`/api/v1/reports/${workspace.report_id}/observation/apply-insights`, { method: 'POST' })
      if (data.workspace) setWorkspace(data.workspace)
      await loadWorkspace()
      await loadSummary()
      return data
    } catch (err) {
      setError(err.message || 'Could not apply insights')
      return null
    } finally {
      setSaving(false)
    }
  }

  async function reloadEvidence() {
    if (!workspace?.report_id) return
    const ev = await apiFetch(`/api/v1/reports/${workspace.report_id}/evidence-summary`).catch(() => null)
    setEvidence(ev)
  }

  return {
    summary,
    workspace,
    preview,
    evidence,
    candidates,
    insights,
    loading,
    error,
    saving,
    loadSummary,
    loadWorkspace,
    loadPreview,
    refresh,
    startReport,
    patchSection,
    submitReport,
    generateInsights,
    applyInsights,
    reloadEvidence,
    addGoalCandidate,
    addStrategyCandidate,
    searchStrategies,
    saveDraft,
    AUTO_SAVE_MS,
  }
}

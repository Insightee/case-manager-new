import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

export function useProgressReport(caseId) {
  const [summary, setSummary] = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [refreshPreview, setRefreshPreview] = useState(null)

  const loadSummary = useCallback(async () => {
    if (!caseId) return null
    const data = await apiFetch(`/api/v1/cases/${caseId}/reports/progress/summary`)
    setSummary(data)
    return data
  }, [caseId])

  const loadWorkspace = useCallback(async () => {
    if (!caseId) return null
    const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/progress`)
    setWorkspace(ws)
    return ws
  }, [caseId])

  const loadPreview = useCallback(async (mode = 'parent') => {
    const id = workspace?.report_id || summary?.report_id
    if (!id) return null
    const data = await apiFetch(`/api/v1/reports/${id}/preview?mode=${mode}`)
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
    } catch (err) {
      setError(err.message || 'Could not load progress report')
    } finally {
      setLoading(false)
    }
  }, [caseId, loadSummary, loadWorkspace])

  useEffect(() => {
    refresh('summary')
  }, [refresh])

  async function startReport() {
    setSaving(true)
    setError('')
    try {
      const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/progress/start`, { method: 'POST' })
      setWorkspace(ws)
      await loadSummary()
      return ws
    } catch (err) {
      setError(err.message || 'Could not start progress report')
      throw err
    } finally {
      setSaving(false)
    }
  }

  async function populateFromEvidence() {
    if (!workspace?.report_id) return null
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/reports/${workspace.report_id}/progress/populate-from-evidence`, {
        method: 'POST',
      })
      if (result.workspace) setWorkspace(result.workspace)
      await loadSummary()
      return result
    } catch (err) {
      setError(err.message || 'Could not compile evidence for this period')
      return null
    } finally {
      setSaving(false)
    }
  }

  async function refreshEvidence() {
    if (!workspace?.report_id) return null
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/reports/${workspace.report_id}/progress/refresh-evidence`, {
        method: 'POST',
      })
      if (result.workspace) setWorkspace(result.workspace)
      setRefreshPreview(result.refresh_preview || null)
      await loadSummary()
      return result
    } catch (err) {
      setError(err.message || 'Could not refresh evidence for this period')
      return null
    } finally {
      setSaving(false)
    }
  }

  async function patchGoal(goalId, patch) {
    if (!workspace?.report_id) return
    setSaving(true)
    setError('')
    try {
      await apiFetch(`/api/v1/reports/${workspace.report_id}/progress/goals/${goalId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      await loadWorkspace()
    } catch (err) {
      setError(err.message || 'Could not save goal status')
    } finally {
      setSaving(false)
    }
  }

  async function fetchGoalEvidence(goalId) {
    if (!workspace?.report_id) return null
    return apiFetch(`/api/v1/reports/${workspace.report_id}/progress/goals/${goalId}/evidence`)
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

  return {
    summary,
    workspace,
    preview,
    loading,
    error,
    saving,
    refreshPreview,
    loadSummary,
    loadWorkspace,
    loadPreview,
    refresh,
    startReport,
    populateFromEvidence,
    refreshEvidence,
    patchGoal,
    fetchGoalEvidence,
    patchSection,
    submitReport,
  }
}

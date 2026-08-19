import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { AI_ENABLED } from '../../../lib/reportsRevampFlags.js'
import { normalizeClinicalApiError } from '../shared/ClinicalReportNotice.jsx'

export const AUTO_SAVE_MS = 5 * 60 * 1000

export function useIepReport(caseId) {
  const [summary, setSummary] = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [preview, setPreview] = useState(null)
  const [availableGoals, setAvailableGoals] = useState(null)
  const [pendingChanges, setPendingChanges] = useState([])
  const [suggestions, setSuggestions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)

  useEffect(() => {
    savingRef.current = saving
  }, [saving])

  const loadSummary = useCallback(async () => {
    if (!caseId) return null
    const data = await apiFetch(`/api/v1/cases/${caseId}/reports/iep/summary`)
    setSummary(data)
    return data
  }, [caseId])

  const loadWorkspace = useCallback(async () => {
    if (!caseId) return null
    try {
      const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/iep`)
      setWorkspace(ws)
      if (ws.report_id) {
        const [goals, pending] = await Promise.all([
          apiFetch(`/api/v1/cases/${caseId}/reports/iep/available-goals`).catch(() => null),
          apiFetch(`/api/v1/reports/${ws.report_id}/iep/pending-changes`).catch(() => ({ items: [] })),
        ])
        setAvailableGoals(goals)
        setPendingChanges(pending?.items || [])
      }
      return ws
    } catch (err) {
      if (err.status === 404) {
        setWorkspace(null)
        setError(normalizeClinicalApiError(err, 'IEP'))
        return null
      }
      throw err
    }
  }, [caseId])

  const loadPreview = useCallback(
    async (mode = 'clinical', reportId) => {
      const id = reportId || workspace?.report_id || summary?.report_id
      if (!id) return null
      const url =
        mode === 'parent'
          ? `/api/v1/reports/${id}/iep/preview?mode=parent`
          : `/api/v1/reports/${id}/iep/preview`
      const data = await apiFetch(url)
      setPreview(data)
      return data
    },
    [workspace?.report_id, summary?.report_id],
  )

  const refresh = useCallback(
    async (mode = 'summary') => {
      if (!caseId) return
      setLoading(true)
      setError('')
      try {
        if (mode === 'summary') await loadSummary()
        else if (mode === 'workspace') await loadWorkspace()
        else if (mode === 'preview') await loadPreview('clinical')
      } catch (err) {
        setError(normalizeClinicalApiError(err, 'IEP'))
      } finally {
        setLoading(false)
      }
    },
    [caseId, loadSummary, loadWorkspace, loadPreview],
  )

  useEffect(() => {
    refresh('summary')
  }, [refresh])

  async function startReport() {
    setSaving(true)
    setError('')
    try {
      const ws = await apiFetch(`/api/v1/cases/${caseId}/reports/iep/start`, { method: 'POST' })
      setWorkspace(ws)
      await loadSummary()
      return ws
    } catch (err) {
      setError(err.message || 'Could not start IEP')
      throw err
    } finally {
      setSaving(false)
    }
  }

  async function generateFromObservation() {
    if (!workspace?.report_id) return
    setSaving(true)
    try {
      const res = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/generate-draft`, { method: 'POST' })
      setWorkspace(res.workspace)
      await loadSummary()
      return res
    } catch (err) {
      setError(err.message || 'Could not import from observation')
      throw err
    } finally {
      setSaving(false)
    }
  }

  async function patchSection(sectionKey, patch) {
    if (!workspace?.report_id) return
    setSaving(true)
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

  async function addGoal(payload) {
    const res = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/goals`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    await loadWorkspace()
    return res
  }

  async function patchGoal(iepGoalId, payload) {
    const res = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/goals/${iepGoalId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    await loadWorkspace()
    return res
  }

  async function deleteGoal(iepGoalId) {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/goals/${iepGoalId}`, { method: 'DELETE' })
    await loadWorkspace()
  }

  async function linkStrategy(iepGoalId, strategyId, strategySourceType = 'repository') {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/goals/${iepGoalId}/strategies`, {
      method: 'POST',
      body: JSON.stringify({ strategy_id: strategyId, strategy_source_type: strategySourceType }),
    })
    await loadWorkspace()
  }

  async function markAchieved(iepGoalId) {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/goals/${iepGoalId}/mark-achieved`, { method: 'POST' })
    await loadWorkspace()
    await loadSummary()
  }

  async function approveChanges(changeIds) {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/approve-changes`, {
      method: 'POST',
      body: JSON.stringify({ change_ids: changeIds }),
    })
    await loadWorkspace()
    await loadSummary()
  }

  async function returnChanges(changeIds, comment) {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/return-changes`, {
      method: 'POST',
      body: JSON.stringify({ change_ids: changeIds, comment }),
    })
    await loadWorkspace()
  }

  async function submitReport() {
    setSaving(true)
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

  async function approveReport(shareWithParent = false) {
    await apiFetch(`/api/v1/reports/${workspace.report_id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ share_with_parent: shareWithParent }),
    })
    await loadWorkspace()
    await loadSummary()
  }

  async function saveDraft() {
    if (!workspace?.report_id) return null
    setSaving(true)
    try {
      const ws = await apiFetch(`/api/v1/reports/${workspace.report_id}/save-draft`, { method: 'POST' })
      setWorkspace(ws)
      return ws
    } finally {
      setSaving(false)
    }
  }

  async function generateSuggestions() {
    if (!workspace?.report_id) return null
    const data = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/generate-suggestions`, { method: 'POST' })
    setSuggestions(data)
    return data
  }

  async function sendForStakeholderApproval() {
    if (!workspace?.report_id) return null
    const res = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/send-for-stakeholder-approval`, { method: 'POST' })
    setWorkspace(res.workspace)
    return res
  }

  async function stakeholderApprove(role) {
    const id = workspace?.report_id || summary?.report_id
    if (!id) return null
    const res = await apiFetch(`/api/v1/reports/${id}/iep/stakeholder-approve?role=${role}`, { method: 'POST' })
    await loadWorkspace().catch(() => loadPreview('parent', id))
    await loadSummary()
    return res
  }

  async function stakeholderRequestReview(role, comment) {
    const id = workspace?.report_id || summary?.report_id
    if (!id) return null
    const res = await apiFetch(`/api/v1/reports/${id}/iep/stakeholder-request-review?role=${role}`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    })
    await loadWorkspace().catch(() => loadPreview('parent', id))
    await loadSummary()
    return res
  }

  async function cmResendForApproval(comment) {
    const res = await apiFetch(`/api/v1/reports/${workspace.report_id}/iep/resend-for-approval`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    })
    setWorkspace(res.workspace)
    return res
  }

  async function patchClinicalInsights(patch) {
    const sec = workspace?.sections?.find((s) => s.key === 'clinical_insights')
    const data = { ...(sec?.structured_data || {}), ...patch }
    await patchSection('clinical_insights', { structured_data: data })
  }

  return {
    summary,
    workspace,
    preview,
    availableGoals,
    pendingChanges,
    suggestions,
    loading,
    error,
    saving,
    setError,
    loadSummary,
    loadWorkspace,
    loadPreview,
    refresh,
    startReport,
    generateFromObservation,
    patchSection,
    addGoal,
    patchGoal,
    deleteGoal,
    linkStrategy,
    markAchieved,
    approveChanges,
    returnChanges,
    submitReport,
    approveReport,
    saveDraft,
    generateSuggestions,
    sendForStakeholderApproval,
    stakeholderApprove,
    stakeholderRequestReview,
    cmResendForApproval,
    patchClinicalInsights,
    AUTO_SAVE_MS,
    aiEnabled: AI_ENABLED,
  }
}

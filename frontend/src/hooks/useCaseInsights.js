import { useCallback, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useCaseInsightsSummary(caseId, options = {}) {
  return useQuery({
    queryKey: queryKeys.caseInsights(caseId),
    queryFn: () => apiFetch(`/api/v1/cases/${caseId}/insights/case-summary`),
    enabled: !!caseId && options.enabled !== false,
    staleTime: 30_000,
  })
}

export function useCaseInsightsUsage(caseId, options = {}) {
  return useQuery({
    queryKey: queryKeys.caseInsightsUsage(caseId),
    queryFn: () => apiFetch(`/api/v1/cases/${caseId}/insights/usage`),
    enabled: !!caseId && options.enabled !== false,
    staleTime: 15_000,
  })
}

/**
 * Composes the Insights tab data layer: the always-available structured summary, the weekly
 * "Refresh Insights" AI-polish cap, insight-card selection state, and the "add selected to
 * report/IEP review" staging mutation. AI is never required to render this tab — `refresh()`
 * only requests wording polish on top of the already-rendered rule-based cards.
 */
export function useCaseInsights(caseId) {
  const queryClient = useQueryClient()
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [refreshMessage, setRefreshMessage] = useState('')

  const summaryQuery = useCaseInsightsSummary(caseId)
  const usageQuery = useCaseInsightsUsage(caseId)

  const toggleSelected = useCallback((insightId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(insightId)) next.delete(insightId)
      else next.add(insightId)
      return next
    })
  }, [])

  const clearSelected = useCallback(() => setSelectedIds(new Set()), [])

  const refreshMutation = useMutation({
    mutationFn: () => apiFetch(`/api/v1/cases/${caseId}/insights/refresh`, { method: 'POST' }),
    onSuccess: (data) => {
      setRefreshMessage(data?.message || '')
      void queryClient.invalidateQueries({ queryKey: queryKeys.caseInsightsUsage(caseId) })
      if (!data?.capExceeded) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.caseInsights(caseId) })
      }
    },
    onError: (err) => {
      setRefreshMessage(err?.message || 'Could not refresh insights. Try again.')
    },
  })

  const selectForReportMutation = useMutation({
    mutationFn: ({ insightIds, destination }) =>
      apiFetch(`/api/v1/cases/${caseId}/insights/select-for-report`, {
        method: 'POST',
        body: JSON.stringify({ insight_ids: insightIds, destination }),
      }),
    onSuccess: () => {
      clearSelected()
    },
  })

  const insights = useMemo(() => summaryQuery.data?.insights || [], [summaryQuery.data])
  const insightsById = useMemo(() => {
    const map = new Map()
    for (const item of insights) map.set(item.id, item)
    return map
  }, [insights])

  const submitSelected = useCallback(
    (destination) => {
      const insightIds = Array.from(selectedIds)
      if (!insightIds.length) return Promise.resolve(null)
      return selectForReportMutation.mutateAsync({ insightIds, destination })
    },
    [selectedIds, selectForReportMutation],
  )

  return {
    summary: summaryQuery.data,
    isLoading: summaryQuery.isLoading,
    isError: summaryQuery.isError,
    refetch: summaryQuery.refetch,
    usage: usageQuery.data,
    insights,
    insightsById,
    selectedIds,
    toggleSelected,
    clearSelected,
    refresh: refreshMutation.mutate,
    isRefreshing: refreshMutation.isPending,
    refreshMessage,
    submitSelected,
    isSubmittingSelection: selectForReportMutation.isPending,
  }
}

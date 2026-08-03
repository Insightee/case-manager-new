import { useCallback, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export const INSIGHTS_ASK_PROMPTS = [
  'What should I focus on next session?',
  'Which strategies need adapting?',
  'Summarize parent concerns this week',
  'What evidence is missing for monthly report?',
]

export function useCaseInsightsAskUsage(caseId, options = {}) {
  return useQuery({
    queryKey: queryKeys.caseInsightsAskUsage(caseId),
    queryFn: () => apiFetch(`/api/v1/cases/${caseId}/insights/ask-usage`),
    enabled: !!caseId && options.enabled !== false,
    staleTime: 15_000,
  })
}

export function useCaseInsightsAsk(caseId) {
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState([])

  const usageQuery = useCaseInsightsAskUsage(caseId)

  const askMutation = useMutation({
    mutationFn: (question) =>
      apiFetch(`/api/v1/cases/${caseId}/insights/ask`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      }),
    onSuccess: (data, question) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.caseInsightsAskUsage(caseId) })
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: question },
        {
          role: 'assistant',
          text: data?.capExceeded
            ? data.message
            : data?.answer || 'Could not find an answer from the latest case context.',
        },
      ])
    },
  })

  const ask = useCallback(
    (question) => {
      const q = (question || '').trim()
      if (!q || askMutation.isPending) return
      askMutation.mutate(q)
    },
    [askMutation],
  )

  return {
    messages,
    ask,
    isAsking: askMutation.isPending,
    askError: askMutation.error?.message || null,
    usage: usageQuery.data,
    isUsageLoading: usageQuery.isLoading,
  }
}

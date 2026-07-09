import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useCaseReportsSummary(caseId, options = {}) {
  return useQuery({
    queryKey: queryKeys.caseReportsSummary(caseId),
    queryFn: () => apiFetch(`/api/v1/cases/${caseId}/reports/summary`),
    enabled: !!caseId && options.enabled !== false,
    staleTime: 30_000,
  })
}

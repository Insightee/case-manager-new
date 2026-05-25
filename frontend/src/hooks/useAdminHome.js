import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useAdminHome() {
  return useQuery({
    queryKey: queryKeys.adminHome,
    queryFn: () => apiFetch('/api/v1/admin/home'),
    staleTime: 60_000,
  })
}

export function useCaseTimeline(caseId) {
  return useQuery({
    queryKey: queryKeys.caseTimeline(caseId),
    queryFn: () => apiFetch(`/api/v1/admin/cases/${caseId}/timeline`),
    enabled: Boolean(caseId),
  })
}

export function useEntityAudit(entityType, entityId, limit = 5) {
  return useQuery({
    queryKey: queryKeys.auditEntity(entityType, entityId),
    queryFn: () =>
      apiFetch('/api/v1/admin/audit', {
        params: { entity_type: entityType, entity_id: String(entityId), limit },
      }),
    enabled: Boolean(entityType && entityId),
  })
}

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useAdminCmHome() {
  return useQuery({
    queryKey: queryKeys.adminCmHome,
    queryFn: () => apiFetch('/api/v1/admin/cm/home'),
    staleTime: 60_000,
  })
}

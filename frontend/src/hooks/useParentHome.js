import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useParentHome() {
  return useQuery({
    queryKey: queryKeys.parentHome,
    queryFn: () => apiFetch('/api/v1/parent/home'),
  })
}

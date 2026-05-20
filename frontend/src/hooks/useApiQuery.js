import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'

export function useApiQuery(key, path, options = {}) {
  return useQuery({
    queryKey: Array.isArray(key) ? key : [key],
    queryFn: () => apiFetch(path),
    staleTime: 30_000,
    ...options,
  })
}

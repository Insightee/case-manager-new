import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { queryKeys } from '../lib/queryClient.js'

export function useTherapistHome() {
  return useQuery({
    queryKey: queryKeys.therapistHome,
    queryFn: () => apiFetch('/api/v1/therapist/home'),
  })
}

export function useTherapistSessionsWorkspace() {
  return useQuery({
    queryKey: queryKeys.therapistWorkspace,
    queryFn: () => apiFetch('/api/v1/therapist/sessions/workspace'),
  })
}

export function useTherapistReportsPipeline() {
  return useQuery({
    queryKey: queryKeys.therapistReportsPipeline,
    queryFn: () => apiFetch('/api/v1/therapist/reports/pipeline'),
  })
}

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { focusRefetchLive, queryKeys } from '../lib/queryClient.js'

export function useTherapistHome() {
  return useQuery({
    queryKey: queryKeys.therapistHome,
    queryFn: () => apiFetch('/api/v1/therapist/home'),
    // Today's sessions: a CM change should show soon after the therapist returns to the app.
    refetchOnWindowFocus: focusRefetchLive,
  })
}

export function useTherapistSessionsWorkspace() {
  return useQuery({
    queryKey: queryKeys.therapistWorkspace,
    queryFn: () => apiFetch('/api/v1/therapist/sessions/workspace'),
    // Session marking (start / end / log) workspace.
    refetchOnWindowFocus: focusRefetchLive,
  })
}

export function useTherapistReportsPipeline() {
  return useQuery({
    queryKey: queryKeys.therapistReportsPipeline,
    queryFn: () => apiFetch('/api/v1/therapist/reports/pipeline'),
  })
}

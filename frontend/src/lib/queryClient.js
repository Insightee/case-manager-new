import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: true,
    },
  },
})

export const queryKeys = {
  therapistHome: ['therapist', 'home'],
  therapistWorkspace: ['therapist', 'sessions', 'workspace'],
  therapistDailyLogs: (userId) => ['therapist', 'daily-logs', userId ?? 'self'],
  therapistReportsPipeline: ['therapist', 'reports', 'pipeline'],
  parentHome: ['parent', 'home'],
  parentCases: ['parent', 'cases'],
  parentBootstrap: ['parent', 'bootstrap'],
  parentAppointments: ['parent', 'appointments'],
  adminHome: ['admin', 'home'],
  adminCmHome: ['admin', 'cm', 'home'],
  notifications: (unreadOnly) => ['notifications', { unreadOnly }],
  caseTimeline: (caseId) => ['admin', 'case', caseId, 'timeline'],
  auditEntity: (entityType, entityId) => ['admin', 'audit', entityType, entityId],
  caseDocuments: (caseId) => ['case', caseId, 'documents'],
  caseDocument: (documentId) => ['case', 'document', documentId],
  parentDocuments: ['parent', 'documents'],
}

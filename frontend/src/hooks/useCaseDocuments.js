import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiUpload } from '../lib/apiClient.js'
import { patchCaseDocumentDetail } from '../lib/caseDocumentCache.js'
import { queryKeys } from '../lib/queryClient.js'

function documentsPath(caseId, filters = {}) {
  const params = new URLSearchParams()
  if (filters.category) params.set('category', filters.category)
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return `/api/v1/cases/${caseId}/documents${qs ? `?${qs}` : ''}`
}

export function useCaseDocumentsList(caseId, filters = {}, options = {}) {
  return useQuery({
    queryKey: [...queryKeys.caseDocuments(caseId), filters],
    queryFn: () => apiFetch(documentsPath(caseId, filters)),
    enabled: !!caseId && (options.enabled !== false),
    staleTime: 30_000,
  })
}

export function useCaseDocumentDetail(documentId, options = {}) {
  return useQuery({
    queryKey: queryKeys.caseDocument(documentId),
    queryFn: () => apiFetch(`/api/v1/documents/${documentId}`),
    enabled: !!documentId && options.enabled !== false,
    staleTime: 15_000,
  })
}

export function useParentDocumentsList(options = {}) {
  return useQuery({
    queryKey: queryKeys.parentDocuments,
    queryFn: async () => {
      const data = await apiFetch('/api/v1/parent/documents')
      return data?.items ?? []
    },
    enabled: options.enabled !== false,
    staleTime: 30_000,
  })
}

export function useCaseDocumentMutations(caseId) {
  const queryClient = useQueryClient()

  const invalidateCase = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.caseDocuments(caseId) })
  }

  const create = useMutation({
    mutationFn: async ({ json, formData }) => {
      if (formData) return apiUpload(`/api/v1/cases/${caseId}/documents`, formData)
      return apiFetch(`/api/v1/cases/${caseId}/documents`, {
        method: 'POST',
        body: JSON.stringify(json),
      })
    },
    onSuccess: (doc) => {
      patchCaseDocumentDetail(doc)
      invalidateCase()
    },
  })

  const patch = useMutation({
    mutationFn: ({ documentId, body }) =>
      apiFetch(`/api/v1/documents/${documentId}`, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: (doc) => {
      patchCaseDocumentDetail(doc)
    },
  })

  const workflow = useMutation({
    mutationFn: ({ documentId, action, body }) =>
      apiFetch(`/api/v1/documents/${documentId}/workflow/${action}`, {
        method: 'POST',
        body: JSON.stringify(body || {}),
      }),
    onSuccess: (doc) => {
      patchCaseDocumentDetail(doc)
    },
  })

  const addVersion = useMutation({
    mutationFn: ({ documentId, formData }) =>
      apiUpload(`/api/v1/documents/${documentId}/versions`, formData),
    onSuccess: (doc) => {
      patchCaseDocumentDetail(doc)
    },
  })

  const addComment = useMutation({
    mutationFn: ({ documentId, body, comment_type }) =>
      apiFetch(`/api/v1/documents/${documentId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body, comment_type: comment_type || 'GENERAL' }),
      }),
  })

  return { create, patch, workflow, addVersion, addComment, invalidateCase }
}

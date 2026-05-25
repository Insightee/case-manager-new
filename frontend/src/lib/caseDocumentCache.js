import { queryClient, queryKeys } from './queryClient.js'

export function applyDocToList(list, doc) {
  if (!doc?.id) return list
  const arr = Array.isArray(list) ? list : []
  const idx = arr.findIndex((d) => d.id === doc.id)
  if (idx >= 0) {
    const next = [...arr]
    next[idx] = { ...next[idx], ...doc }
    return next
  }
  return [doc, ...arr]
}

export function applyCommentToDetail(detail, comment) {
  if (!detail || !comment?.id) return detail
  const comments = Array.isArray(detail.comments) ? detail.comments : []
  if (comments.some((c) => c.id === comment.id)) return detail
  return { ...detail, comments: [...comments, comment] }
}

export function patchCaseDocumentsList(caseId, doc) {
  if (!caseId || !doc) return
  queryClient.setQueryData(queryKeys.caseDocuments(caseId), (old) => applyDocToList(old, doc))
  void queryClient.invalidateQueries({ queryKey: queryKeys.caseDocuments(caseId) })
}

export function patchCaseDocumentDetail(doc) {
  if (!doc?.id) return
  queryClient.setQueryData(queryKeys.caseDocument(doc.id), doc)
  if (doc.case_id) patchCaseDocumentsList(doc.case_id, doc)
}

export function patchParentDocumentsList(items, doc) {
  const arr = Array.isArray(items) ? items : []
  queryClient.setQueryData(queryKeys.parentDocuments, applyDocToList(arr, doc))
  void queryClient.invalidateQueries({ queryKey: queryKeys.parentDocuments })
}

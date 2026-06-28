/** Role visibility for Clinical Brain surfaces (frontend guardrails). */

const THERAPIST_ROLES = new Set(['THERAPIST'])
const CM_ROLES = new Set(['CASE_MANAGER', 'SUPERVISOR', 'ADMIN', 'SUPER_ADMIN'])
const ADMIN_ROLES = new Set(['ADMIN', 'SUPER_ADMIN'])
const PARENT_ROLES = new Set(['PARENT', 'SCHOOL_COORDINATOR'])

export function primaryRole(user) {
  const names = user?.role_names || user?.roles || []
  return names[0] || user?.role || ''
}

export function isTherapist(user) {
  return THERAPIST_ROLES.has(primaryRole(user))
}

export function isCaseManager(user) {
  return CM_ROLES.has(primaryRole(user))
}

export function isClinicalLead(user) {
  return ADMIN_ROLES.has(primaryRole(user))
}

export function isParent(user) {
  return PARENT_ROLES.has(primaryRole(user))
}

export function canApproveOrgPool(user) {
  return isClinicalLead(user) || isCaseManager(user)
}

export function canMergeBankItems(user) {
  return isClinicalLead(user)
}

export function canViewInternalEvidence(user) {
  return !isParent(user)
}

export function canViewAiAudit(user) {
  return isClinicalLead(user)
}

export function canSendToCmReview(user) {
  return isTherapist(user) || isCaseManager(user)
}

export function canProposeCaseGoal(user) {
  return isTherapist(user) || isCaseManager(user)
}

export function filterParentSafeGoals(items) {
  return (items || []).filter((g) => g.parent_safe !== false && g.visibility !== 'internal_only')
}

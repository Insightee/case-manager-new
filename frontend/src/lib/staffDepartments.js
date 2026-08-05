/** Staff department tags — keep ids aligned with backend/app/core/departments.py */

export const STAFF_DEPARTMENTS = [
  { id: 'FINANCE', label: 'Finance' },
  { id: 'HR', label: 'HR' },
  { id: 'ONBOARDING', label: 'Onboarding' },
  { id: 'TRAINING', label: 'Training' },
  { id: 'CLIENT', label: 'Client' },
  { id: 'MARKETING', label: 'Marketing' },
  { id: 'OPERATIONS', label: 'Operations' },
  { id: 'LEADERSHIP', label: 'Leadership' },
  { id: 'TECH', label: 'Tech' },
  { id: 'MENTORS', label: 'Mentors' },
  { id: 'ONBOARDING_MENTORS', label: 'Onboarding Mentors' },
  { id: 'REVIEW_AND_COMPLIANCE', label: 'Review and Compliance' },
  { id: 'CASE_MANAGERS', label: 'Case Managers' },
]

const LABEL_BY_ID = Object.fromEntries(STAFF_DEPARTMENTS.map((d) => [d.id, d.label]))

export function staffDepartmentLabel(departmentId, departments = STAFF_DEPARTMENTS) {
  if (!departmentId) return null
  const id = String(departmentId).toUpperCase()
  const fromList = (departments || STAFF_DEPARTMENTS).find((d) => d.id === id)
  return fromList?.label || LABEL_BY_ID[id] || null
}

export function normalizeStaffDepartments(departments) {
  if (Array.isArray(departments) && departments.length) return departments
  return STAFF_DEPARTMENTS
}

import { CaseSchedulingHub } from './CaseSchedulingHub.jsx'

export function AdminCaseSchedulingPanel({ caseItem, assignments, onDone }) {
  return <CaseSchedulingHub caseItem={caseItem} assignments={assignments} onDone={onDone} canBook />
}

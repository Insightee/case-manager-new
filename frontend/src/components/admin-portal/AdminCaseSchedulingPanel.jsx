import { CaseSchedulingHub } from './CaseSchedulingHub.jsx'

export function AdminCaseSchedulingPanel({ caseItem, assignments, onDone, onCaseUpdated, canAssign, canEditBilling }) {
  return (
    <CaseSchedulingHub
      caseItem={caseItem}
      assignments={assignments}
      onDone={onDone}
      onCaseUpdated={onCaseUpdated}
      canBook
      canAssign={canAssign}
      canEditBilling={canEditBilling}
    />
  )
}

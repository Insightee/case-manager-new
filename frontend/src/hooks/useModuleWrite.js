import { useCallback, useMemo } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { clinicalProductModuleIds } from '../lib/moduleAccess.js'

/** Per-module write helpers for admin mutation buttons. */
export function useModuleWrite() {
  const { user, can, canWriteProduct, canWriteFeature, isViewOnly } = useAuth()

  const canWriteBilling = useMemo(
    () => can('invoice.approve') && !isViewOnly && canWriteFeature('invoices'),
    [can, isViewOnly, canWriteFeature],
  )

  const canCreateProductCase = useCallback(
    (productModule) => can('case.create') && !isViewOnly && canWriteProduct(productModule),
    [can, isViewOnly, canWriteProduct],
  )

  const canEditProductCase = useCallback(
    (productModule) => can('case.update') && !isViewOnly && canWriteProduct(productModule),
    [can, isViewOnly, canWriteProduct],
  )

  const canAssignProductCase = useCallback(
    (productModule) => can('case.assign') && !isViewOnly && canWriteProduct(productModule),
    [can, isViewOnly, canWriteProduct],
  )

  const canReviewReports = useCallback(
    (productModule) =>
      can('monthly_report.approve') && !isViewOnly && canWriteFeature('reports', productModule),
    [can, isViewOnly, canWriteFeature],
  )

  const canEditIep = useCallback(
    (productModule) => can('iep.read') && !isViewOnly && canWriteFeature('iep', productModule),
    [can, isViewOnly, canWriteFeature],
  )

  const canReviewLogs = useCallback(
    (productModule) => can('daily_log.review') && !isViewOnly && canWriteFeature('session_logs', productModule),
    [can, isViewOnly, canWriteFeature],
  )

  const canManageTickets = useCallback(
    (productModule) => can('ticket.manage') && !isViewOnly && canWriteFeature('tickets', productModule),
    [can, isViewOnly, canWriteFeature],
  )

  const canManageUsers = useMemo(
    () => can('user.manage') && !isViewOnly,
    [can, isViewOnly],
  )

  const canReviewAnyClinicalReports = useCallback(() => {
    for (const pid of clinicalProductModuleIds(user)) {
      if (canReviewReports(pid)) return true
    }
    return false
  }, [user, canReviewReports])

  return {
    isViewOnly,
    canManageUsers,
    canWriteBilling,
    canCreateProductCase,
    canEditProductCase,
    canAssignProductCase,
    canReviewReports,
    canEditIep,
    canReviewLogs,
    canManageTickets,
    canReviewAnyClinicalReports,
  }
}

/** Derive a navigation path from entity_type + entity_id + portal. */
export function resolveNotificationLink(entityType, entityId, portal) {
  if (!entityType) return null
  const et = entityType.toLowerCase()
  switch (et) {
    case 'appointment':
    case 'recurring_schedule':
    case 'invite':
      if (portal === 'parent') return '/parent/book'
      if (portal === 'therapist') return '/therapist/slots'
      return '/admin/cases'
    case 'therapist_slot':
    case 'slot':
      if (portal === 'parent') return '/parent/book'
      if (portal === 'therapist') return '/therapist/slots'
      return '/admin/cases'
    case 'session':
    case 'daily_log':
      if (portal === 'parent') return '/parent/session-logs'
      if (portal === 'therapist') return '/therapist/logs'
      return '/admin/logs'
    case 'invoice':
    case 'client_invoice':
      if (portal === 'parent') return '/parent/billing'
      return '/admin/invoices'
    case 'case':
      if (portal === 'parent' && entityId) return `/parent/cases/${entityId}`
      if (portal === 'admin' && entityId) return `/admin/cases/${entityId}`
      if (portal === 'therapist' && entityId) return `/therapist/cases/${entityId}`
      return portal === 'parent' ? '/parent' : '/admin/cases'
    case 'monthly_report':
    case 'report':
      if (portal === 'parent') return '/parent/reports'
      if (portal === 'therapist') return '/therapist/reports'
      if (entityId) {
        const p = new URLSearchParams({ reportId: String(entityId) })
        if (entityType === 'observation_report') p.set('type', 'observation')
        else p.set('type', 'monthly')
        return `/admin/reports?${p.toString()}`
      }
      return '/admin/reports'
    case 'iep':
    case 'iep_document':
      if (portal === 'parent') return '/parent/reports?type=iep'
      return '/admin/iep'
    case 'leave':
    case 'therapist_leave':
      if (portal === 'therapist') return '/therapist/leave'
      if (portal === 'admin') return '/admin/leave'
      return '/hr/leave'
    case 'support_ticket':
    case 'ticket':
      if (portal === 'parent') return '/parent/support'
      if (portal === 'therapist') return '/therapist/support'
      return '/admin/support?tab=tickets'
    case 'incident':
      if (portal === 'therapist') return '/therapist/support'
      if (portal === 'parent') return '/parent/support'
      if (entityId) return `/admin/support?tab=incidents&incident=${entityId}`
      return '/admin/support?tab=incidents'
    case 'case_manager_meeting':
    case 'cm_meeting':
      if (portal === 'parent') return '/parent/book'
      if (portal === 'therapist') return '/therapist/cm-meetings'
      return '/admin/cm-meetings'
    case 'user':
    case 'invite_token':
      return '/admin/people'
    case 'payout':
      return portal === 'therapist' ? '/therapist/invoices' : '/admin/invoices'
    default:
      return null
  }
}

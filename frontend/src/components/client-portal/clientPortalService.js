import clientCasesData from '../../data/clientCases.json'
import clientReportsData from '../../data/clientReports.json'
import clientIepData from '../../data/clientIepStatus.json'
import clientBillingData from '../../data/clientBilling.json'

const auditEvents = []

function canAccessParentData(currentParentId, payloadParentId) {
  return currentParentId && currentParentId === payloadParentId
}

function withParentScope(currentParentId, payload) {
  if (!canAccessParentData(currentParentId, payload.parentId)) {
    return []
  }

  return payload
}

export function getParentCases(currentParentId) {
  const scoped = withParentScope(currentParentId, clientCasesData)
  return scoped.cases ?? []
}

export function getApprovedReports(currentParentId) {
  const scoped = withParentScope(currentParentId, clientReportsData)
  return (scoped.reports ?? []).filter((item) => item.status === 'approved')
}

export function getIepStatus(currentParentId) {
  const scoped = withParentScope(currentParentId, clientIepData)
  return scoped.items ?? []
}

export function getBillingSummaries(currentParentId) {
  const scoped = withParentScope(currentParentId, clientBillingData)
  return scoped.items ?? []
}

export function recordParentAuditEvent(type, payload = {}) {
  auditEvents.push({
    id: `evt-${Date.now()}-${auditEvents.length + 1}`,
    type,
    timestamp: new Date().toISOString(),
    payload,
  })
}

export function getParentAuditEvents() {
  return auditEvents
}

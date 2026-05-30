/** Mirrors backend support_hub_capabilities for UI gating. */
export function tabsFromCapabilities(cap) {
  if (!cap?.tabs) return []
  const out = []
  if (cap.tabs.tickets) out.push({ id: 'tickets', label: 'Tickets' })
  if (cap.tabs.incidents) out.push({ id: 'incidents', label: 'Incidents' })
  if (cap.tabs.history) out.push({ id: 'reports', label: 'History' })
  return out
}

export function isOwnSupportScope(cap) {
  return cap?.scope === 'own'
}

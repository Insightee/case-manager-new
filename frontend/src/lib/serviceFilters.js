export const SERVICE_OPTIONS = [
  { value: '', label: 'All services' },
  { value: 'homecare', label: 'Homecare' },
  { value: 'shadow_support', label: 'Shadow support' },
]

export function serviceLabel(value) {
  return SERVICE_OPTIONS.find((o) => o.value === value)?.label || value || 'All services'
}

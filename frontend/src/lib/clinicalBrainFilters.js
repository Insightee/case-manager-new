import { GOAL_MODAL_DOMAIN_CHIPS } from './clinicalUiContract.js'
import { CORE_ENVIRONMENTS } from './coreClinicalTaxonomy.js'

export const SUPPORT_NEED_OPTIONS = [
  { id: 'transitions', label: 'Transitions' },
  { id: 'requesting_help', label: 'Requesting help' },
  { id: 'self_advocacy', label: 'Self-advocacy' },
  { id: 'peer_participation', label: 'Peer participation' },
  { id: 'task_initiation', label: 'Task initiation' },
  { id: 'sensory_overload', label: 'Sensory overload' },
  { id: 'emotional_regulation', label: 'Emotional regulation' },
  { id: 'aac_use', label: 'AAC use' },
  { id: 'classroom_participation', label: 'Classroom participation' },
  { id: 'avoidance', label: 'Refusal / avoidance' },
  { id: 'anxiety_demands', label: 'Anxiety around demands' },
  { id: 'daily_routines', label: 'Daily routines' },
  { id: 'safety', label: 'Safety' },
  { id: 'toileting', label: 'Toileting' },
  { id: 'mealtime', label: 'Mealtime' },
]

export const SERVICE_TYPE_OPTIONS = [
  { id: 'shadow_support', label: 'Shadow support' },
  { id: 'homecare', label: 'Homecare' },
  { id: 'center', label: 'Center-based' },
  { id: 'school', label: 'School' },
]

export const AGE_GROUP_OPTIONS = [
  { id: 'early_years', label: 'Early years' },
  { id: 'primary', label: 'Primary' },
  { id: 'middle', label: 'Middle school' },
  { id: 'secondary', label: 'Secondary' },
]

export const SUPPORT_LEVEL_OPTIONS = [
  { id: 'independent', label: 'Independent' },
  { id: 'visual_support', label: 'Visual support' },
  { id: 'verbal_support', label: 'Verbal support' },
  { id: 'gestural_support', label: 'Gesture support' },
  { id: 'physical_support', label: 'Physical support' },
  { id: 'co_regulation', label: 'Co-regulation needed' },
]

export const BANK_STATUS_TABS = [
  { id: 'active', label: 'Active' },
  { id: 'drafts', label: 'Drafts' },
  { id: 'candidates', label: 'Candidates' },
  { id: 'needs_review', label: 'Needs review' },
  { id: 'deprecated', label: 'Deprecated' },
]

export const POOL_STATUS_TABS = [
  { id: 'active', label: 'Active' },
  { id: 'candidates', label: 'Candidates' },
  { id: 'needs_review', label: 'Needs review' },
  { id: 'deprecated', label: 'Deprecated' },
]

export const REVIEW_QUEUE_TABS = [
  { id: 'goal_candidates', label: 'Goal candidates' },
  { id: 'strategy_candidates', label: 'Strategy candidates' },
  { id: 'missing_evidence', label: 'Missing evidence' },
  { id: 'language_flags', label: 'Language flags' },
  { id: 'reports', label: 'Reports needing review' },
  { id: 'returned', label: 'Returned items' },
]

export const DOMAIN_OPTIONS = GOAL_MODAL_DOMAIN_CHIPS.map((d) => ({ id: d.id, label: d.label }))
export const ENVIRONMENT_OPTIONS = CORE_ENVIRONMENTS.map((e) => ({ id: e.id, label: e.label }))

export const EMPTY_FILTERS = {
  query: '',
  domain: '',
  supportNeed: '',
  environment: '',
  serviceType: '',
  ageGroup: '',
  supportLevel: '',
  status: '',
  evidenceStrength: '',
}

export function applyClinicalFilters(items, filters, getters = {}) {
  const q = (filters.query || '').trim().toLowerCase()
  return (items || []).filter((item) => {
    const domain = getters.domain?.(item) || item.domain_key || (item.core_domains || [])[0] || ''
    const support = getters.supportNeed?.(item) || item.support_need || item.rationale || ''
    const env = getters.environment?.(item) || item.environment_context || (item.core_environments || [])[0] || ''
    const label = getters.label?.(item) || item.label || item.title || ''
    if (filters.domain && domain !== filters.domain) return false
    if (filters.supportNeed && !String(support).toLowerCase().includes(filters.supportNeed)) return false
    if (filters.environment && env !== filters.environment) return false
    if (filters.serviceType && item.service_type !== filters.serviceType) return false
    if (filters.ageGroup && item.age_group !== filters.ageGroup) return false
    if (filters.supportLevel && item.support_level !== filters.supportLevel) return false
    if (filters.status && item._filter_status !== filters.status && item.status !== filters.status) return false
    if (q && !label.toLowerCase().includes(q)) return false
    return true
  })
}

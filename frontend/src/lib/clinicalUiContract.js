/**
 * Clinical UI contract — single source for report builder + goal modal.
 * Domain and environment tabs MUST match Observation Report (see iepObservationAlign.js).
 */
import { CORE_ENVIRONMENTS } from './coreClinicalTaxonomy.js'
import { IEP_DOMAIN_TABS } from './iepObservationAlign.js'

export const GOAL_MODAL_TABS = [
  { id: 'templates', label: 'Templates' },
  { id: 'custom', label: 'Custom goal' },
]

export const GOAL_MODAL_DOMAIN_CHIPS = [
  { id: 'communication_aac', label: 'Communication' },
  { id: 'peer_social', label: 'Social' },
  { id: 'independence', label: 'Independence' },
  { id: 'emotional_regulation', label: 'Regulation' },
  { id: 'academics_learning', label: 'Academics' },
  { id: 'environment_supports', label: 'Sensory' },
]

export const IEP_BUILDER_SECTIONS = [
  { key: 'child_context', num: '01', title: 'Client profile & core administration' },
  { key: 'clinical_insights', num: '02', title: 'Clinical insights from observations' },
  { key: 'priority_domains', num: '03', title: 'Domains' },
  { key: 'strategies_accommodations', num: '04', title: 'Learning environments & supports' },
  { key: 'goals_plan', num: '05', title: 'Active & proposed goals' },
  { key: 'talent_development', num: '06', title: 'Strengths & growth opportunities' },
  { key: 'review_parent_plan', num: '07', title: 'Service & implementation plan' },
]

/** @deprecated use IEP_DOMAIN_TABS from iepObservationAlign.js */
export const PRESENT_LEVEL_TABS = IEP_DOMAIN_TABS

/** Learning environments — same ids as session log / CORE_ENVIRONMENTS */
export const IEP_LEARNING_ENVIRONMENTS = CORE_ENVIRONMENTS.map((e) => ({ id: e.id, label: e.label }))

/** @deprecated use IEP_LEARNING_ENVIRONMENTS */
export const ENVIRONMENT_TABS = IEP_LEARNING_ENVIRONMENTS

export const DEFERRED_ACTIONS = new Set(['duplicate'])

/**
 * Mock / fallback data shaped like goal_repository_items, strategy_repository_items, etc.
 * TODO(backend): replace with dedicated bank/pool/review APIs when available.
 */

import { GOAL_MODAL_DOMAIN_CHIPS } from './clinicalUiContract.js'

export const MOCK_GOAL_TEMPLATES = [
  {
    id: 'tpl-transition-1',
    label: 'Request a break using AAC or gesture',
    domain_key: 'communication_aac',
    support_need: 'transitions',
    parent_meaning: 'Your child can ask for a pause when things feel busy.',
    goal_statement: 'During structured activities, the child will request a break using AAC or an agreed gesture.',
    related_strategies_count: 3,
    source: 'repository',
    environments: ['classroom', 'home'],
    service_type: 'shadow_support',
    age_group: 'primary',
  },
  {
    id: 'tpl-peer-1',
    label: 'Initiate peer interaction with visual support',
    domain_key: 'peer_social',
    support_need: 'peer_participation',
    parent_meaning: 'Your child is practising ways to join play with a friend.',
    goal_statement: 'With visual support, the child will initiate a brief peer interaction during group activities.',
    related_strategies_count: 2,
    source: 'repository',
    environments: ['classroom', 'playground'],
    service_type: 'shadow_support',
    age_group: 'primary',
  },
  {
    id: 'tpl-reg-1',
    label: 'Use co-regulation before transitions',
    domain_key: 'emotional_regulation',
    support_need: 'emotional_regulation',
    parent_meaning: 'A trusted adult helps your child feel ready before changing activities.',
    goal_statement: 'The child will participate in a brief co-regulation routine before classroom transitions.',
    related_strategies_count: 4,
    source: 'repository',
    environments: ['classroom'],
    service_type: 'homecare',
    age_group: 'early_years',
  },
]

export const MOCK_STRATEGY_POOL = [
  {
    id: 'pool-visual-countdown',
    label: 'Visual countdown before transition',
    purpose: 'Gives predictable time before changing activities',
    domain_key: 'emotional_regulation',
    support_need: 'transitions',
    environments: ['classroom', 'home'],
    support_level: 'visual_support',
    evidence_label: 'commonly_used',
    caution: 'May need longer countdown in noisy settings',
    linked_goal_domain: 'emotional_regulation',
    usage_count: 12,
    status: 'approved',
    scope: 'organization',
  },
  {
    id: 'pool-first-then',
    label: 'First-then board',
    purpose: 'Shows what happens now and what comes next',
    domain_key: 'communication_aac',
    support_need: 'task_initiation',
    environments: ['classroom', 'therapy_room'],
    support_level: 'visual_support',
    evidence_label: 'emerging',
    linked_goal_domain: 'communication_aac',
    usage_count: 4,
    status: 'approved',
    scope: 'organization',
  },
  {
    id: 'pool-break-card',
    label: 'Break card / pause signal',
    purpose: 'Supports self-advocacy for regulation',
    domain_key: 'communication_aac',
    support_need: 'self_advocacy',
    environments: ['classroom', 'home'],
    support_level: 'gestural_support',
    evidence_label: 'new',
    usage_count: 1,
    status: 'approved',
    scope: 'organization',
  },
]

export const MOCK_PARENT_GOALS = [
  {
    id: 'pg-1',
    focus_area: 'Transitions between activities',
    parent_explanation:
      'We are helping your child feel ready before moving from one activity to another.',
    what_helps: 'Visual countdown, extra time, and a calm check-in from a trusted adult.',
    what_we_notice: 'More participation when transitions are previewed ahead of time.',
    home_school_support: 'Use the same countdown language at home before leaving play or meals.',
    last_shared_date: '2026-06-15',
    parent_safe: true,
  },
  {
    id: 'pg-2',
    focus_area: 'Peer connection',
    parent_explanation: 'We are building safe ways to join play with classmates.',
    what_helps: 'Structured turn-taking games and a visual invitation script.',
    what_we_notice: 'Brief engagement increases when a peer buddy is available.',
    home_school_support: 'Arrange short playdates with predictable games.',
    last_shared_date: '2026-06-10',
    parent_safe: true,
  },
]

export function enrichGoalTemplatesFromApi(items = []) {
  if (items.length) {
    return items.map((g) => ({
      ...g,
      support_need: g.support_need || g.rationale?.split(' ')[0]?.toLowerCase() || 'transitions',
      parent_meaning: g.parent_meaning || g.desired_state || g.goal_statement,
      related_strategies_count: g.related_strategies_count ?? 0,
      source: g.scope === 'organization' ? 'repository' : g.source || 'template',
    }))
  }
  return MOCK_GOAL_TEMPLATES
}

export function enrichStrategyPoolFromApi(items = []) {
  if (items.length) {
    return items.map((s) => ({
      ...s,
      purpose: s.purpose || s.when_to_use || s.expected_outcome,
      evidence_label: s.evidence_label || (s.evidence_count >= 5 ? 'commonly_used' : s.evidence_count >= 2 ? 'emerging' : 'new'),
    }))
  }
  return MOCK_STRATEGY_POOL
}

export function domainLabel(id) {
  return GOAL_MODAL_DOMAIN_CHIPS.find((d) => d.id === id)?.label || id
}

/** Map strategy picker selection to clinical_extension-compatible shape */
export function strategySelectionToExtension(selection) {
  return {
    strategy_status: selection.used_as === 'adapted' ? 'adapted_today' : selection.used_as === 'not_used' ? 'not_used' : 'used_as_planned',
    child_response: selection.child_response || null,
    adaptation_note: selection.evidence_note || '',
    field_provenance: {},
  }
}

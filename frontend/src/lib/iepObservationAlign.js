/**
 * IEP ↔ Observation alignment — domain tabs match observation report section keys.
 */

/** Same keys as observation report domain narrative sections. */
export const IEP_DOMAIN_TABS = [
  { id: 'communication', label: 'Communication' },
  { id: 'regulation_sensory', label: 'Regulation & Sensory' },
  { id: 'participation', label: 'Participation' },
  { id: 'learning_access', label: 'Learning Access' },
  { id: 'peer_interaction', label: 'Social / Peer Interaction' },
]

/** IEP learning environments — capability-based (not session-log place presets). */
export const IEP_LEARNING_ENVIRONMENTS = [
  { id: 'home', label: 'Home' },
  { id: 'school', label: 'School' },
  { id: 'physical', label: 'Physical' },
  { id: 'intellectual', label: 'Intellectual' },
  { id: 'social', label: 'Social' },
  { id: 'creative', label: 'Creative' },
  { id: 'emotional', label: 'Emotional' },
]

export const OBSERVATION_ENVIRONMENT_PRESETS = ['Playground', 'Peer Relationships', 'Classroom', 'Home']

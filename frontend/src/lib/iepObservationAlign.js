/**
 * IEP ↔ Observation alignment — domain tabs match observation report section keys.
 */
import { CORE_ENVIRONMENTS } from './coreClinicalTaxonomy.js'

/** Same keys as observation report domain narrative sections. */
export const IEP_DOMAIN_TABS = [
  { id: 'communication', label: 'Communication' },
  { id: 'regulation_sensory', label: 'Regulation & Sensory' },
  { id: 'participation', label: 'Participation' },
  { id: 'learning_access', label: 'Learning Access' },
  { id: 'peer_interaction', label: 'Social / Peer Interaction' },
]

export const IEP_LEARNING_ENVIRONMENTS = CORE_ENVIRONMENTS.map((e) => ({
  id: e.id,
  label: e.label,
}))

export const OBSERVATION_ENVIRONMENT_PRESETS = ['Playground', 'Peer Relationships', 'Classroom', 'Home']

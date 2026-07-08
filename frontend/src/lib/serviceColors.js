/** Shared service-line colours for therapist case surfaces. */

import { moduleLabel } from './moduleLabels.js'

export const SERVICE_STYLES = {
  homecare: {
    label: 'Homecare',
    tone: 'homecare',
    bg: '#dcfce7',
    text: '#166534',
    border: '#86efac',
  },
  shadow_support: {
    label: 'Shadow support',
    tone: 'shadow',
    bg: '#ede9fe',
    text: '#5b21b6',
    border: '#c4b5fd',
  },
  counselling: {
    label: 'Counselling',
    tone: 'counselling',
    bg: '#e0f2fe',
    text: '#0369a1',
    border: '#7dd3fc',
  },
  special_education: {
    label: 'Special education',
    tone: 'special-ed',
    bg: '#fef3c7',
    text: '#b45309',
    border: '#fcd34d',
  },
  behaviour_therapy: {
    label: 'Behaviour therapy',
    tone: 'behaviour',
    bg: '#ffe4e6',
    text: '#be123c',
    border: '#fda4af',
  },
  tutoring: {
    label: 'Tutoring',
    tone: 'tutoring',
    bg: '#f0fdfa',
    text: '#0f766e',
    border: '#5eead4',
  },
  other: {
    label: 'Other',
    tone: 'other',
    bg: '#f1f5f9',
    text: '#475569',
    border: '#cbd5e1',
  },
}

function normalizeServiceKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/-/g, '_')
}

export function resolveServiceKey(service, productModule) {
  const candidates = [productModule, service].map(normalizeServiceKey).filter(Boolean)
  for (const key of candidates) {
    if (SERVICE_STYLES[key]) return key
    if (key.includes('shadow')) return 'shadow_support'
    if (key.includes('home')) return 'homecare'
    if (key.includes('counsel') || key.includes('counsell')) return 'counselling'
    if (key.includes('special')) return 'special_education'
    if (key.includes('behav')) return 'behaviour_therapy'
    if (key.includes('tutor')) return 'tutoring'
  }
  return 'other'
}

export function serviceStyle(service, productModule) {
  const key = resolveServiceKey(service, productModule)
  const label =
    moduleLabel(productModule) ||
    moduleLabel(key) ||
    String(service || productModule || SERVICE_STYLES[key].label)
  return {
    key,
    label,
    tone: SERVICE_STYLES[key].tone,
    bg: SERVICE_STYLES[key].bg,
    text: SERVICE_STYLES[key].text,
    border: SERVICE_STYLES[key].border,
  }
}

export function serviceStyleFromCase(caseRow = {}) {
  return serviceStyle(caseRow.service || caseRow.service_type, caseRow.productModule || caseRow.product_module)
}

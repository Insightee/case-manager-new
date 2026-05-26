export const PERFORMANCE_DOMAINS = [
  { key: 'academic', label: 'Academic' },
  { key: 'social', label: 'Social' },
  { key: 'speech', label: 'Speech' },
  { key: 'behavioral', label: 'Behavioral' },
  { key: 'self_help', label: 'Self-help' },
  { key: 'motor', label: 'Motor' },
  { key: 'sensory', label: 'Sensory' },
  { key: 'other', label: 'Other' },
]

export const LEARNING_STYLES = [
  { key: 'visual', label: 'Visual' },
  { key: 'auditory', label: 'Auditory' },
  { key: 'kinesthetic', label: 'Kinesthetic' },
  { key: 'multimodal', label: 'Multimodal' },
]

const EMPTY_ENV = { environment: '', strengths: '', goals: '', strategies: '', supports_needed: '' }

export function emptySections() {
  return {
    schema_version: 2,
    header: {
      child_name: '',
      age_label: '',
      diagnosis: '',
      service_provided: '',
      parents_names: '',
      therapist_name: '',
      school_or_home_name: '',
      class_grade: '',
      date_of_evaluation: '',
      date_of_iep_meeting: '',
      review_date: '',
      about_child_brief: '',
    },
    observations: '',
    learning_environments: [{ ...EMPTY_ENV }, { ...EMPTY_ENV }],
    challenges: '',
    current_performance: PERFORMANCE_DOMAINS.map((d) => ({ domain: d.key, notes: '' })),
    learning_style: { styles: [], elaboration: '' },
    interventions: '',
    talent_development: { strengths: '', goals: '', strategies: '', areas_of_need: '' },
    other_areas_of_need: { strengths: '', goals: '', strategies: '', areas_of_need: '' },
    intervention_by_insighte: '',
    verification: {
      therapist_verified: false,
      therapist_name: '',
      therapist_date: '',
      therapist_license_no: '',
      case_manager_name: '',
      case_manager_date: '',
      client_name: '',
      client_date: '',
    },
  }
}

/** Normalize API sections (v1 legacy or v2) into editable v2 shape. */
export function normalizeSections(raw, caseContext) {
  const base = emptySections()
  if (!raw) {
    if (caseContext) applyContext(base, caseContext)
    return base
  }
  if (raw.schema_version >= 2 && raw.header) {
    const merged = {
      ...base,
      ...raw,
      header: { ...base.header, ...(raw.header || {}) },
      learning_style: { ...base.learning_style, ...(raw.learning_style || {}) },
      talent_development: { ...base.talent_development, ...(raw.talent_development || {}) },
      other_areas_of_need: { ...base.other_areas_of_need, ...(raw.other_areas_of_need || {}) },
      verification: { ...base.verification, ...(raw.verification || {}) },
    }
    if (!merged.learning_environments?.length) {
      merged.learning_environments = [{ ...EMPTY_ENV }]
    }
    if (!merged.current_performance?.length) {
      merged.current_performance = base.current_performance
    }
    if (!merged.challenges && raw.referral) merged.challenges = raw.referral
    if (!merged.header.about_child_brief && raw.about_child) {
      merged.header.about_child_brief = raw.about_child
    }
    return merged
  }
  const legacy = {
    ...base,
    header: {
      ...base.header,
      about_child_brief: raw.about_child || '',
    },
    challenges: raw.referral || raw.challenges || '',
    observations: raw.observations || '',
    learning_environments:
      raw.learning_environments?.length > 0
        ? raw.learning_environments.map((r) => ({
            environment: r.environment || '',
            strengths: r.strengths || '',
            goals: r.goals || '',
            strategies: r.strategies || '',
            supports_needed: r.supports_needed || '',
          }))
        : base.learning_environments,
    interventions: raw.interventions || '',
    verification: {
      ...base.verification,
      therapist_name: raw.signatures || '',
    },
  }
  if (caseContext) applyContext(legacy, caseContext)
  return legacy
}

function applyContext(sections, ctx) {
  const h = sections.header
  if (!h.child_name && ctx.child_name) h.child_name = ctx.child_name
  if (!h.age_label && ctx.age_label) h.age_label = ctx.age_label
  if (!h.diagnosis && ctx.diagnosis) h.diagnosis = ctx.diagnosis
  if (!h.service_provided && ctx.service_provided) h.service_provided = ctx.service_provided
  if (!h.parents_names && ctx.parents_names) h.parents_names = ctx.parents_names
  if (!h.therapist_name && ctx.therapist_name) h.therapist_name = ctx.therapist_name
  if (!h.school_or_home_name && ctx.school_or_home_name) h.school_or_home_name = ctx.school_or_home_name
  if (!h.class_grade && ctx.class_grade) h.class_grade = ctx.class_grade
  if (!sections.observations && ctx.observations_text) sections.observations = ctx.observations_text
  if (!sections.verification.therapist_license_no && ctx.therapist_license_no) {
    sections.verification.therapist_license_no = ctx.therapist_license_no
  }
}

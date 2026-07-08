/**
 * Case Overview data composition — read-only aggregation from existing sources.
 *
 * Section mapping (no overview-specific schema):
 * - Header / snapshot: CaseRead, assignments, iep-plan case_context, service_location_type
 * - Summary: case_clinical_profiles.history, observation/IEP narrative fallbacks
 * - Strengths & interests: case_clinical_profiles, observation report sections
 * - Support context: clinical profile diagnosis, observation sections, case service_type
 * - Support needs: observation support_needs, clinical profile (neuro-affirmative phrasing)
 * - Current goals: clinical-quality-summary goal_coverage + iep-plan performance domains (active IEP)
 * - Care team: case assignments + case_manager_name on CaseRead
 * - Pending work: clinical-quality-summary missing_items + report_statuses
 * - Missing info: derived gaps from the same sources above
 */

import { moduleLabel, caseServiceLine } from './moduleLabels.js'
import { formatDisplayDate } from './datetime.js'

const ACTIVE_IEP_STATUSES = new Set(['APPROVED', 'SHARED_WITH_PARENT', 'PARENT_ACKNOWLEDGED'])

function splitLines(text) {
  if (!text) return []
  return String(text)
    .split(/[\n,;•]+/)
    .map((s) => s.replace(/^[-*]\s*/, '').trim())
    .filter(Boolean)
}

function stripHtml(text) {
  return String(text || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function observationResponses(observation) {
  return observation?.responses || {}
}

function sectionNarrative(observation, key) {
  const responses = observationResponses(observation)
  const direct = responses[key]
  if (direct) return stripHtml(direct)
  const sec = (observation?.sections || []).find((s) => s.key === key)
  return stripHtml(sec?.narrative_text || sec?.structured_data?.text || '')
}

function structuredList(observation, key, field) {
  const sec = (observation?.sections || []).find((s) => s.key === key)
  const data = sec?.structured_data || {}
  const list = data[field]
  if (Array.isArray(list)) return list.filter(Boolean).map(String)
  return splitLines(data[field] || sectionNarrative(observation, key))
}

function formatLocationType(value) {
  if (!value) return null
  const map = {
    HOME: 'Home',
    SCHOOL: 'School',
    CLINIC: 'Clinic',
    COMMUNITY: 'Community',
    ONLINE: 'Online',
  }
  return map[value] || String(value).replace(/_/g, ' ')
}

function therapistStartedLabel(assignments = []) {
  const active = assignments.filter((a) => a.status === 'ACTIVE' || !a.end_date)
  if (!active.length) return null
  const earliest = [...active].sort((a, b) => String(a.start_date).localeCompare(String(b.start_date)))[0]
  return earliest?.start_date ? formatDisplayDate(earliest.start_date) : null
}

function careTeamFromSources(caseRow, assignments = []) {
  const team = []
  const activeAssignments = assignments.filter((a) => a.status === 'ACTIVE' || !a.end_date)

  const primary = activeAssignments[0]
  if (primary?.therapist_name) {
    team.push({ key: 'primary', name: primary.therapist_name, role: 'Primary therapist' })
  } else if (caseRow?.therapist_name) {
    team.push({ key: 'primary', name: caseRow.therapist_name, role: 'Primary therapist' })
  }

  if (caseRow?.case_manager_name) {
    team.push({ key: 'cm', name: caseRow.case_manager_name, role: 'Case manager' })
  }

  activeAssignments.slice(1).forEach((a, idx) => {
    if (a.therapist_name) {
      team.push({ key: `other-${a.id || idx}`, name: a.therapist_name, role: 'Therapist' })
    }
  })

  if (caseRow?.parent_name) {
    team.push({ key: 'parent', name: caseRow.parent_name, role: 'Parent' })
  }

  return team
}

function currentGoalsFromSources(qualitySummary, iepPlan) {
  const hasActiveIep =
    qualitySummary?.report_statuses?.has_active_iep ||
    ACTIVE_IEP_STATUSES.has(qualitySummary?.report_statuses?.iep_status)

  const fromCoverage = (qualitySummary?.goal_coverage || [])
    .filter((g) => g.label)
    .map((g) => ({
      id: g.label,
      title: g.label,
      meta: g.sessions_addressed
        ? `${g.sessions_addressed} session${g.sessions_addressed === 1 ? '' : 's'} with evidence`
        : null,
    }))

  if (fromCoverage.length) return { goals: fromCoverage, hasActiveIep }

  if (!iepPlan || !hasActiveIep) return { goals: [], hasActiveIep: false }

  const domains = iepPlan?.sections?.current_performance || []
  const goals = domains
    .filter((d) => d?.goals?.trim() || d?.domain)
    .map((d, idx) => ({
      id: `domain-${idx}`,
      title: d.domain || `Goal area ${idx + 1}`,
      meta: stripHtml(d.goals) || null,
    }))

  return { goals, hasActiveIep }
}

function overviewSummaryText({ clinicalProfile, observation, iepPlan }) {
  const history = clinicalProfile?.history?.trim()
  if (history) return history

  const obsNarrative =
    sectionNarrative(observation, 'referral_background') ||
    sectionNarrative(observation, 'child_snapshot')
  if (obsNarrative) return obsNarrative

  const iepObs = stripHtml(iepPlan?.sections?.observations || '')
  if (iepObs) return iepObs

  const about = stripHtml(iepPlan?.sections?.header?.about_child_brief || '')
  if (about) return about

  return null
}

function strengthsList({ clinicalProfile, observation }) {
  const fromProfile = splitLines(clinicalProfile?.strengths)
  const fromObs = structuredList(observation, 'strengths_interests', 'strengths')
  const merged = [...new Set([...fromProfile, ...fromObs])]
  return merged
}

function interestsList({ clinicalProfile, observation }) {
  const fromProfile = splitLines(clinicalProfile?.interests)
  const fromObs = structuredList(observation, 'strengths_interests', 'interests')
  return [...new Set([...fromProfile, ...fromObs])]
}

function supportNeedsList({ observation }) {
  const fromObs = splitLines(sectionNarrative(observation, 'support_needs'))
  return fromObs.slice(0, 8)
}

export function composeCaseOverview({
  caseId,
  caseRow,
  clinicalProfile,
  qualitySummary,
  assignments = [],
  iepPlan = null,
  observation = null,
}) {
  const serviceLine =
    caseServiceLine(caseRow?.service_type, caseRow?.product_module) ||
    moduleLabel(caseRow?.product_module) ||
    caseRow?.service_type ||
    null
  const ageLabel = iepPlan?.case_context?.age_label || null
  const primarySetting =
    formatLocationType(caseRow?.service_location_type) ||
    (iepPlan?.sections?.learning_environments?.[0]?.environment
      ? String(iepPlan.sections.learning_environments[0].environment)
      : null)

  const strengths = strengthsList({ clinicalProfile, observation })
  const interests = interestsList({ clinicalProfile, observation })
  const supportNeeds = supportNeedsList({ clinicalProfile, observation })
  const { goals, hasActiveIep } = currentGoalsFromSources(qualitySummary, iepPlan)
  const careTeam = careTeamFromSources(caseRow, assignments)
  const parentPriorities = splitLines(sectionNarrative(observation, 'parent_inputs'))

  const diagnosisProfile =
    clinicalProfile?.diagnosis?.trim() ||
    stripHtml(iepPlan?.case_context?.diagnosis || iepPlan?.sections?.header?.diagnosis || '') ||
    null

  const therapyAreas = [caseRow?.service_type, serviceLine].filter(Boolean)
  const uniqueTherapyAreas = [...new Set(therapyAreas)]

  const missingInfo = []
  if (!strengths.length) missingInfo.push({ id: 'strengths', label: 'Strengths not added yet' })
  if (!interests.length) missingInfo.push({ id: 'interests', label: 'Interests not added yet' })
  if (!parentPriorities.length) missingInfo.push({ id: 'parent_priorities', label: 'Parent priorities missing' })
  if (!goals.length) missingInfo.push({ id: 'goals', label: 'Current goals missing' })
  if (!primarySetting) missingInfo.push({ id: 'setting', label: 'Primary setting missing' })
  if (!caseRow?.case_manager_name || !assignments.length) {
    missingInfo.push({ id: 'care_team', label: 'Care team incomplete' })
  }

  const pendingWork = buildPendingWork(qualitySummary, caseRow)

  return {
    caseId,
    header: {
      childName: caseRow?.child_name || 'Client',
      ageLabel,
      caseCode: caseRow?.case_code,
      serviceLine,
      status: caseRow?.status,
      primarySetting,
    },
    snapshot: {
      clientSince: caseRow?.created_at ? formatDisplayDate(caseRow.created_at) : null,
      therapistStarted: therapistStartedLabel(assignments),
      primarySetting,
      serviceLine,
    },
    summary: overviewSummaryText({ clinicalProfile, observation, iepPlan }),
    strengths,
    interests,
    supportContext: {
      diagnosisProfile,
      therapyAreas: uniqueTherapyAreas,
      communicationSupports: splitLines(sectionNarrative(observation, 'support_needs')).slice(0, 4),
      primarySetting,
    },
    supportNeeds,
    goals,
    hasActiveIep,
    careTeam,
    pendingWork,
    missingInfo,
    parentPriorities,
  }
}

function buildPendingWork(qualitySummary, caseRow) {
  const items = []
  const missing = qualitySummary?.missing_items || []
  const rs = qualitySummary?.report_statuses || {}

  if (missing.includes('session_logs')) {
    const count = qualitySummary?.evidence_summary?.sessions_without_goal_entries || 1
    items.push({
      id: 'session_logs',
      title: count > 1 ? `${count} session logs` : 'Session log',
      subtitle: 'Visit ended — log still needed',
      action: 'Complete',
      tab: 'logs',
    })
  }

  if (missing.includes('monthly_report_current_month')) {
    items.push({
      id: 'monthly_report',
      title: rs.current_month ? `${rs.current_month} monthly report` : 'Monthly report',
      subtitle: String(rs.current_month_status || '').toUpperCase() === 'DRAFT' ? 'Continue draft' : 'Start this month’s report',
      action: String(rs.current_month_status || '').toUpperCase() === 'DRAFT' ? 'Continue' : 'Start',
      tab: 'reports',
      section: 'monthly',
    })
  } else if (
    String(rs.current_month_status || '').toUpperCase() === 'DRAFT' ||
    String(rs.current_month_status || '').toUpperCase() === 'REJECTED'
  ) {
    items.push({
      id: 'monthly_report_draft',
      title: rs.current_month ? `${rs.current_month} monthly report` : 'Monthly report',
      subtitle: String(rs.current_month_status || '').toUpperCase() === 'REJECTED' ? 'Revision requested' : 'Ready to review',
      action: 'Open',
      tab: 'reports',
      section: 'dashboard',
    })
  }

  if (missing.includes('custom_items_pending_review')) {
    items.push({
      id: 'custom_review',
      title: 'Goals or strategies',
      subtitle: 'Items awaiting case manager review',
      action: 'Review',
      tab: 'goals',
    })
  }

  if (missing.includes('observation_checklist')) {
    items.push({
      id: 'observation',
      title: 'Observation report',
      subtitle: 'Initial observation still in progress',
      action: 'Open',
      tab: 'reports',
      section: 'observation',
    })
  }

  if (missing.includes('active_iep')) {
    items.push({
      id: 'iep',
      title: 'IEP plan',
      subtitle: 'Active goal plan not in place yet',
      action: 'Build',
      tab: 'reports',
      section: 'iep',
    })
  }

  if (caseRow?.status === 'ACTIVE' && !caseRow?.billing_updated_at && caseRow?.client_billing_amount) {
    items.push({
      id: 'billing',
      title: 'Billing setup',
      subtitle: 'Confirm billing details for this case',
      action: 'Review',
      tab: 'overview',
    })
  }

  return items
}

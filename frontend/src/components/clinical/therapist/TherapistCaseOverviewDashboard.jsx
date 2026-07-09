import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { composeCaseOverview } from '../../../lib/caseOverviewCompose.js'
import { CaseOverviewSummaryCard } from './CaseOverviewSummaryCard.jsx'
import '../../../styles/case-overview-v2.css'

function OverviewSection({ icon, title, children, className = '', headActions = null }) {
  return (
    <section className={`cov-card ${className}`.trim()}>
      <div className="cov-card__head">
        <span className="material-symbols-outlined cov-card__icon" aria-hidden="true">
          {icon}
        </span>
        <h3 className="cov-card__title">{title}</h3>
        {headActions}
      </div>
      {children}
    </section>
  )
}

function SnapshotCard({ snapshot }) {
  const rows = [
    { label: 'Age', value: snapshot.ageLabel },
    { label: 'Client since', value: snapshot.clientSince },
    { label: 'Therapist started', value: snapshot.therapistStarted },
    { label: 'Primary setting', value: snapshot.primarySetting },
    { label: 'Service type', value: snapshot.serviceLine },
  ].filter((r) => r.value)

  const pointers = snapshot.clinicalPointers || []

  if (!rows.length && !pointers.length) {
    return (
      <OverviewSection icon="person" title="Profile snapshot">
        <p className="cov-empty">Case dates and setting will appear once the profile is set up.</p>
      </OverviewSection>
    )
  }

  return (
    <OverviewSection icon="person" title="Profile snapshot">
      {rows.length ? (
        <div className="cov-snapshot-block">
          <dl className="cov-kv-list">
            {rows.map((row) => (
              <div key={row.label} className="cov-kv">
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      {pointers.length ? (
        <div className="cov-snapshot-block cov-snapshot-block--clinical">
          <p className="cov-snapshot-block__eyebrow">From observation report</p>
          <ul className="cov-check-list cov-snapshot-pointers">
            {pointers.map((item) => (
              <li key={item}>
                <span className="material-symbols-outlined" aria-hidden="true">
                  arrow_right
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </OverviewSection>
  )
}

function StrengthsBlock({ strengths }) {
  if (!strengths.length) {
    return <p className="cov-empty">Strengths not added yet</p>
  }
  return (
    <ul className="cov-check-list">
      {strengths.map((item) => (
        <li key={item}>
          <span className="material-symbols-outlined" aria-hidden="true">
            check_circle
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function InterestsBlock({ interests }) {
  if (!interests.length) {
    return <p className="cov-empty">Interests not added yet</p>
  }
  return (
    <div className="cov-tag-row">
      {interests.map((item) => (
        <span key={item} className="cov-tag">
          {item}
        </span>
      ))}
    </div>
  )
}

function StrengthsInterestsSection({ strengths, interests }) {
  return (
    <>
      <div className="cov-strengths-combined">
        <OverviewSection icon="star" title="Strengths & interests">
          <StrengthsBlock strengths={strengths} />
          <div className="cov-interests-divider">
            <InterestsBlock interests={interests} />
          </div>
        </OverviewSection>
      </div>
      <div className="cov-strengths-split cov-strengths-grid">
        <OverviewSection icon="verified" title="Strengths">
          <StrengthsBlock strengths={strengths} />
        </OverviewSection>
        <OverviewSection icon="auto_awesome" title="Interests">
          <InterestsBlock interests={interests} />
        </OverviewSection>
      </div>
    </>
  )
}

function SupportContextCard({ supportContext }) {
  const { diagnosisProfile, therapyAreas, communicationSupports, primarySetting } = supportContext
  const hasContent =
    diagnosisProfile ||
    therapyAreas.length ||
    communicationSupports.length ||
    primarySetting

  if (!hasContent) {
    return (
      <OverviewSection icon="clinical_notes" title="Support context">
        <p className="cov-empty">Support context will appear from intake, observation, or IEP.</p>
      </OverviewSection>
    )
  }

  const therapyText = therapyAreas.join(', ')

  return (
    <OverviewSection icon="clinical_notes" title="Support context">
      {diagnosisProfile ? (
        <div className="cov-context-row">
          <span className="material-symbols-outlined" aria-hidden="true">
            psychology
          </span>
          <div>
            <span className="cov-context-row__label">Diagnosis / profile</span>
            <p className="cov-context-row__value">{diagnosisProfile}</p>
          </div>
        </div>
      ) : null}
      {therapyText ? (
        <div className="cov-context-row">
          <span className="material-symbols-outlined" aria-hidden="true">
            medical_services
          </span>
          <div>
            <span className="cov-context-row__label">Therapy areas</span>
            <p className="cov-context-row__value">{therapyText}</p>
          </div>
        </div>
      ) : null}
      {communicationSupports.length ? (
        <div className="cov-context-row">
          <span className="material-symbols-outlined" aria-hidden="true">
            record_voice_over
          </span>
          <div>
            <span className="cov-context-row__label">Communication supports</span>
            <ul className="cov-check-list">
              {communicationSupports.map((item) => (
                <li key={item}>
                  <span className="material-symbols-outlined" aria-hidden="true">
                    check_circle
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
      {primarySetting ? (
        <div className="cov-context-row">
          <span className="material-symbols-outlined" aria-hidden="true">
            location_on
          </span>
          <div>
            <span className="cov-context-row__label">Primary setting</span>
            <p className="cov-context-row__value">{primarySetting}</p>
          </div>
        </div>
      ) : null}
    </OverviewSection>
  )
}

function SupportNeedsCard({ supportNeeds }) {
  return (
    <OverviewSection icon="report_problem" title="Concerns / support needs">
      {supportNeeds.length ? (
        <ul className="cov-needs-list">
          {supportNeeds.map((item) => (
            <li key={item}>
              <span className="material-symbols-outlined" aria-hidden="true">
                warning
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cov-empty">Support needs will appear from intake or observation notes.</p>
      )}
    </OverviewSection>
  )
}

function GoalsCard({ goals, onOpenGoals }) {
  return (
    <OverviewSection
      icon="target"
      title="Current goals"
      headActions={
        goals.length ? (
          <button type="button" className="cov-text-action" onClick={onOpenGoals}>
            Open
          </button>
        ) : null
      }
    >
      {goals.length ? (
        <ul className="cov-goal-list">
          {goals.slice(0, 6).map((goal) => (
            <li key={goal.id} className="cov-goal-row">
              <span className="cov-goal-row__bar" aria-hidden="true" />
              <div className="cov-goal-row__body">
                <p className="cov-goal-row__title">{goal.title}</p>
                {goal.meta ? <p className="cov-goal-row__meta">{goal.meta}</p> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cov-empty cov-empty--plain">No current goals added yet.</p>
      )}
    </OverviewSection>
  )
}

function PendingWorkCard({ items, onAction, className = '' }) {
  if (!items.length) {
    return (
      <OverviewSection icon="pending_actions" title="Pending work" className={className}>
        <p className="cov-empty cov-empty--plain">You are caught up on documentation for this case.</p>
      </OverviewSection>
    )
  }

  return (
    <OverviewSection icon="pending_actions" title="Pending work" className={className}>
      <ul className="cov-pending-list">
        {items.map((item) => {
          const urgent = item.id === 'session_logs'
          return (
            <li
              key={item.id}
              className={`cov-pending-row${urgent ? ' cov-pending-row--urgent' : ''}`}
            >
              <div>
                <p className="cov-pending-row__title">{item.title}</p>
                {item.subtitle ? <p className="cov-pending-row__sub">{item.subtitle}</p> : null}
              </div>
              <button type="button" className="cov-pending-link" onClick={() => onAction(item)}>
                {item.action}
              </button>
            </li>
          )
        })}
      </ul>
    </OverviewSection>
  )
}

function CareTeamCard({ careTeam }) {
  return (
    <OverviewSection icon="groups" title="Care team">
      {careTeam.length ? (
        <ul className="cov-team-list">
          {careTeam.map((person) => (
            <li key={person.key} className="cov-team-row">
              <span className="cov-team-row__role">{person.role}</span>
              <span className="cov-team-row__name">{person.name}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cov-empty">Care team assignments will appear here.</p>
      )}
    </OverviewSection>
  )
}

function MissingInfoCard({ missingInfo }) {
  if (!missingInfo.length) return null

  return (
    <OverviewSection icon="info" title="Missing information">
      <ul className="cov-missing-list">
        {missingInfo.map((item) => (
          <li key={item.id}>
            <span className="material-symbols-outlined" aria-hidden="true">
              error_outline
            </span>
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </OverviewSection>
  )
}

export function TherapistCaseOverviewDashboard({
  caseId,
  caseRow,
  clinicalProfile,
  qualitySummary,
  onOpenTab,
  onClinicalProfileUpdated,
}) {
  const [assignments, setAssignments] = useState([])
  const [iepPlan, setIepPlan] = useState(null)
  const [observation, setObservation] = useState(null)
  const [extrasLoading, setExtrasLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setExtrasLoading(true)
    Promise.all([
      apiFetch(`/api/v1/cases/${caseId}/assignments`).catch(() => []),
      apiFetch(`/api/v1/cases/${caseId}/iep-plan`).catch(() => null),
      apiFetch(`/api/v1/cases/${caseId}/reports/observation`)
        .catch(() => apiFetch(`/api/v1/cases/${caseId}/observation-checklist`).catch(() => null)),
    ]).then(([asg, iep, obs]) => {
      if (cancelled) return
      setAssignments(Array.isArray(asg) ? asg : [])
      setIepPlan(iep)
      setObservation(obs)
      setExtrasLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [caseId])

  const overview = useMemo(
    () =>
      composeCaseOverview({
        caseId,
        caseRow,
        clinicalProfile,
        qualitySummary,
        assignments,
        iepPlan,
        observation,
      }),
    [caseId, caseRow, clinicalProfile, qualitySummary, assignments, iepPlan, observation],
  )

  function handlePendingAction(item) {
    if (!item.tab) return
    onOpenTab(item.tab, item.section ? { section: item.section } : undefined)
  }

  const { snapshot, strengths, interests, supportContext, supportNeeds, goals, careTeam, pendingWork, missingInfo } =
    overview

  return (
    <div className="cov-page forest-light cp-therapist-overview">
      {extrasLoading ? <p className="cov-empty">Loading case context…</p> : null}

      <div className="cov-columns">
        <div className="cov-main">
          <SnapshotCard snapshot={snapshot} />

          <CaseOverviewSummaryCard
            caseId={caseId}
            clinicalProfile={clinicalProfile}
            onProfileUpdated={onClinicalProfileUpdated}
            composedFallback={overview.caseBrief}
            emptyMessage="Add a case brief in the client profile, or complete the observation report to pull one in."
          />

          <PendingWorkCard
            className="cov-pending--mobile"
            items={pendingWork}
            onAction={handlePendingAction}
          />

          <StrengthsInterestsSection strengths={strengths} interests={interests} />
          <SupportContextCard supportContext={supportContext} />
          <SupportNeedsCard supportNeeds={supportNeeds} />
          <GoalsCard goals={goals} onOpenGoals={() => onOpenTab('goals')} />
        </div>

        <aside className="cov-rail">
          <PendingWorkCard
            className="cov-pending--desktop"
            items={pendingWork}
            onAction={handlePendingAction}
          />
          <CareTeamCard careTeam={careTeam} />
          <MissingInfoCard missingInfo={missingInfo} />
        </aside>
      </div>
    </div>
  )
}

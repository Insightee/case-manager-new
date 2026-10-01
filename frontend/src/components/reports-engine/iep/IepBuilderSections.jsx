import { useMemo, useState } from 'react'
import { IEP_BUILDER_SECTIONS } from '../../../lib/clinicalUiContract.js'
import { IEP_DOMAIN_TABS, IEP_LEARNING_ENVIRONMENTS } from '../../../lib/iepObservationAlign.js'
import { IepGoalCard } from './IepGoalCard.jsx'

function sectionData(sections, key) {
  return sections?.find((s) => s.key === key) || {}
}

function structured(sections, key) {
  return sectionData(sections, key).structured_data || {}
}

function DomainFields({ tabId, present, domains, readOnly, onPatchSection }) {
  const row = present[tabId] || {}
  return (
    <>
      {row.source === 'observation_report' ? (
        <p className="text-xs text-lush-forest mb-2 m-0 font-medium">Imported from observation report — you can refine below.</p>
      ) : null}
      <label className="block text-xs font-bold uppercase text-outline mb-1">Strengths</label>
      <textarea
        key={`${tabId}-strengths`}
        className="w-full min-h-[80px] rounded-xl border p-3 text-sm mb-3"
        disabled={readOnly}
        defaultValue={row.strengths || ''}
        placeholder="What works well in this domain…"
        onBlur={(e) =>
          onPatchSection('priority_domains', {
            structured_data: {
              ...domains,
              present_levels: {
                ...present,
                [tabId]: { ...row, strengths: e.target.value, source: row.source || 'iep' },
              },
            },
          })
        }
      />
      <label className="block text-xs font-bold uppercase text-outline mb-1">Support needs</label>
      <textarea
        key={`${tabId}-support`}
        className="w-full min-h-[80px] rounded-xl border p-3 text-sm"
        disabled={readOnly}
        defaultValue={row.support_needs || ''}
        placeholder="Supports that help participation…"
        onBlur={(e) =>
          onPatchSection('priority_domains', {
            structured_data: {
              ...domains,
              present_levels: {
                ...present,
                [tabId]: { ...row, support_needs: e.target.value, source: row.source || 'iep' },
              },
            },
          })
        }
      />
    </>
  )
}

function EnvironmentFields({ envId, envData, readOnly, sections, onPatchSection }) {
  const row = envData.environments?.[envId] || {}
  return (
    <textarea
      key={`env-${envId}`}
      className="w-full min-h-[100px] rounded-xl border p-3 text-sm"
      disabled={readOnly}
      defaultValue={row.notes || ''}
      placeholder="Accommodations and environmental adjustments…"
      onBlur={(e) =>
        onPatchSection('strategies_accommodations', {
          structured_data: {
            ...envData,
            environments: {
              ...(envData.environments || {}),
              [envId]: { label: row.label || IEP_LEARNING_ENVIRONMENTS.find((x) => x.id === envId)?.label, notes: e.target.value },
            },
          },
        })
      }
    />
  )
}

export function IepBuilderSections({
  sections,
  goals,
  childName,
  readOnly,
  variant = 'therapist',
  suggestedGoals = [],
  onPatchSection,
  onEditGoal,
  onRemoveGoal,
  onLinkStrategy,
  onMarkAchieved,
  onAddGoal,
  onImportSuggestedGoal,
}) {
  const [domainTab, setDomainTab] = useState(IEP_DOMAIN_TABS[0].id)
  const [envTab, setEnvTab] = useState(IEP_LEARNING_ENVIRONMENTS[0].id)

  const ctx = sectionData(sections, 'child_context')
  const ctxData = structured(sections, 'child_context')
  const domains = structured(sections, 'priority_domains')
  const present = domains.present_levels || {}
  const envData = structured(sections, 'strategies_accommodations')
  const talent = structured(sections, 'talent_development')
  const service = structured(sections, 'review_parent_plan')
  const reviewSec = sectionData(sections, 'review_parent_plan')

  const isParent = variant === 'parent'
  const isAdmin = variant === 'admin'
  const canEditTherapistInput = !readOnly && !isParent
  const canEditCmNotes = !readOnly && isAdmin
  const reviewDateLocked = Boolean(service.review_date_locked)
  const sectionReadOnly = readOnly || isParent

  const importedStrengths = useMemo(
    () => talent.imported_strengths || (talent.imported_strengths === undefined && talent.strengths ? [] : []),
    [talent],
  )
  const strengthChips = importedStrengths.length ? importedStrengths : []

  const iepGoalLabels = new Set(
    goals.map((g) => (g.title || g.goal_statement || '').trim().toLowerCase()).filter(Boolean),
  )
  const importable = suggestedGoals.filter(
    (g) => g.label && !iepGoalLabels.has((g.label || '').trim().toLowerCase()),
  )

  const sourceLabel = {
    observation: 'Observation report',
    session_log: 'Session logs',
    repository: 'Goal engine',
    iep: 'Active plan',
  }

  return (
    <>
      <section className="cr-section">
        <p className="cr-section__label">
          {IEP_BUILDER_SECTIONS[0].num} · {IEP_BUILDER_SECTIONS[0].title}
        </p>
        <textarea
          className="w-full min-h-[100px] rounded-xl border border-outline-variant/50 p-3 text-sm"
          disabled={readOnly}
          defaultValue={ctx.narrative_text || ''}
          placeholder={`Strengths, care team notes for ${childName || 'client'}…`}
          onBlur={(e) => onPatchSection('child_context', { narrative_text: e.target.value })}
        />
        <div className="grid md:grid-cols-2 gap-3 mt-3 text-sm">
          <input
            className="min-h-[44px] rounded-xl border px-3"
            disabled={readOnly}
            placeholder="Care team lead"
            defaultValue={ctxData.care_team_lead || ''}
            onBlur={(e) =>
              onPatchSection('child_context', {
                structured_data: { ...ctxData, care_team_lead: e.target.value },
              })
            }
          />
          <input
            className="min-h-[44px] rounded-xl border px-3"
            disabled={readOnly}
            placeholder="Primary setting"
            defaultValue={ctxData.primary_setting || ''}
            onBlur={(e) =>
              onPatchSection('child_context', {
                structured_data: { ...ctxData, primary_setting: e.target.value },
              })
            }
          />
        </div>
      </section>

      <section className="cr-section">
        <p className="cr-section__label">
          {IEP_BUILDER_SECTIONS[2].num} · {IEP_BUILDER_SECTIONS[2].title}
        </p>
        <div className="cr-tab-bar" role="tablist">
          {IEP_DOMAIN_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={domainTab === t.id}
              className={`cr-tab${domainTab === t.id ? ' cr-tab--active' : ''}`}
              onClick={() => setDomainTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <DomainFields
          tabId={domainTab}
          present={present}
          domains={domains}
          readOnly={readOnly}
          onPatchSection={onPatchSection}
        />
      </section>

      <section className="cr-section">
        <p className="cr-section__label">
          {IEP_BUILDER_SECTIONS[3].num} · {IEP_BUILDER_SECTIONS[3].title}
        </p>
        <div className="cr-tab-bar" role="tablist">
          {IEP_LEARNING_ENVIRONMENTS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={envTab === t.id}
              className={`cr-tab${envTab === t.id ? ' cr-tab--active' : ''}`}
              onClick={() => setEnvTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <EnvironmentFields
          envId={envTab}
          envData={envData}
          readOnly={readOnly}
          sections={sections}
          onPatchSection={onPatchSection}
        />
      </section>

      <section className="cr-section">
        <div className="flex justify-between items-center flex-wrap gap-2 mb-4">
          <p className="cr-section__label m-0">
            {IEP_BUILDER_SECTIONS[4].num} · {IEP_BUILDER_SECTIONS[4].title}
          </p>
          {!readOnly ? (
            <button type="button" className="cr-btn cr-btn--forest" onClick={onAddGoal}>
              + Add goal
            </button>
          ) : null}
        </div>
        {importable.length > 0 ? (
          <div className="mb-4 p-4 rounded-xl border border-lush-forest/30 bg-lush-mint/10">
            <p className="text-sm font-semibold text-lush-forest m-0 mb-2">Goals already in use on this case</p>
            <ul className="space-y-2 m-0 p-0 list-none">
              {importable.map((g) => (
                <li
                  key={`${g._source}-${g.id || g.label}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/80 px-3 py-2 border border-outline-variant/30"
                >
                  <div>
                    <p className="text-sm font-medium m-0">{g.label}</p>
                    <p className="text-xs text-on-surface-variant m-0">
                      {sourceLabel[g._source] || g._source}
                    </p>
                  </div>
                  {!readOnly ? (
                    <button type="button" className="cr-btn cr-btn--forest text-xs" onClick={() => onImportSuggestedGoal?.(g)}>
                      Add to IEP
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {goals.length === 0 ? (
          <p className="text-sm text-on-surface-variant">Add at least one goal with measurement criteria and linked strategies.</p>
        ) : (
          goals.map((g) => (
            <IepGoalCard
              key={g.iep_goal_id}
              goal={g}
              readOnly={readOnly}
              onEdit={onEditGoal}
              onRemove={onRemoveGoal}
              onLinkStrategy={onLinkStrategy}
              onMarkAchieved={onMarkAchieved}
            />
          ))
        )}
      </section>

      <section className="cr-section">
        <p className="cr-section__label">
          {IEP_BUILDER_SECTIONS[5].num} · {IEP_BUILDER_SECTIONS[5].title}
        </p>
        {strengthChips.length > 0 ? (
          <div className="mb-3">
            <p className="text-xs font-bold uppercase text-outline m-0 mb-2">From observation report</p>
            <div className="flex flex-wrap gap-2">
              {strengthChips.map((s) => (
                <span key={s} className="px-3 py-1 rounded-lg bg-lush-mint/40 text-lush-forest text-sm font-semibold">
                  {s}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase text-outline mb-1">Additional strengths</label>
            <textarea
              className="w-full min-h-[100px] rounded-xl border p-3 text-sm"
              disabled={readOnly}
              placeholder="Strengths to leverage in this plan…"
              defaultValue={talent.additional_strengths || ''}
              onBlur={(e) =>
                onPatchSection('talent_development', {
                  structured_data: { ...talent, additional_strengths: e.target.value },
                })
              }
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase text-outline mb-1">Opportunities to grow</label>
            <textarea
              className="w-full min-h-[100px] rounded-xl border p-3 text-sm"
              disabled={readOnly}
              placeholder="Areas the care team can build on…"
              defaultValue={talent.opportunities || ''}
              onBlur={(e) =>
                onPatchSection('talent_development', {
                  structured_data: { ...talent, opportunities: e.target.value },
                })
              }
            />
          </div>
        </div>
      </section>

      <section className="cr-section">
        <p className="cr-section__label">
          {IEP_BUILDER_SECTIONS[6].num} · {IEP_BUILDER_SECTIONS[6].title}
        </p>
        <textarea
          className="w-full min-h-[80px] rounded-xl border p-3 text-sm mb-3"
          disabled={readOnly}
          placeholder="Service frequency, location, implementation notes…"
          defaultValue={reviewSec.narrative_text || service.plan_notes || ''}
          onBlur={(e) =>
            onPatchSection('review_parent_plan', {
              narrative_text: e.target.value,
              structured_data: { ...service, plan_notes: e.target.value },
            })
          }
        />
        <label className="block text-xs font-bold uppercase text-outline mb-1">Review date for next IEP</label>
        <input
          type="date"
          className="min-h-[44px] rounded-xl border px-3 text-sm mb-4 w-full max-w-xs"
          disabled={sectionReadOnly || reviewDateLocked}
          defaultValue={service.review_date || ''}
          onBlur={(e) =>
            onPatchSection('review_parent_plan', {
              structured_data: { ...service, review_date: e.target.value },
            })
          }
        />
        {reviewDateLocked ? (
          <p className="text-xs text-on-surface-variant mb-4 m-0">Locked after case manager approval.</p>
        ) : null}
        {!isParent ? (
          <>
            <label className="block text-xs font-bold uppercase text-outline mb-1">Therapist input (internal)</label>
            <textarea
              className="w-full min-h-[72px] rounded-xl border p-3 text-sm mb-3"
              disabled={!canEditTherapistInput}
              placeholder="Internal clinical notes — not shared with families…"
              defaultValue={service.therapist_input || ''}
              onBlur={(e) =>
                onPatchSection('review_parent_plan', {
                  structured_data: { ...service, therapist_input: e.target.value },
                })
              }
            />
          </>
        ) : null}
        {(service.parent_inputs || []).length > 0 ? (
          <>
            <label className="block text-xs font-bold uppercase text-outline mb-1">Parent / family input</label>
            <ul className="space-y-2 m-0 p-0 list-none mb-3">
              {service.parent_inputs.map((item) => (
                <li key={item.id} className="text-sm bg-secondary-container/30 rounded-lg p-3 border border-outline-variant/20">
                  <p className="m-0">{item.text}</p>
                </li>
              ))}
            </ul>
          </>
        ) : isParent ? (
          <p className="text-sm text-on-surface-variant mb-3 m-0">Use the family input field on your portal to share priorities.</p>
        ) : null}
        {isAdmin ? (
          <>
            <label className="block text-xs font-bold uppercase text-outline mb-1">Case manager notes (internal)</label>
            <textarea
              className="w-full min-h-[72px] rounded-xl border p-3 text-sm"
              disabled={!canEditCmNotes}
              placeholder="Internal CM notes — not shown to families…"
              defaultValue={service.cm_internal_notes || ''}
              onBlur={(e) =>
                onPatchSection('review_parent_plan', {
                  structured_data: { ...service, cm_internal_notes: e.target.value },
                })
              }
            />
          </>
        ) : null}
      </section>
    </>
  )
}

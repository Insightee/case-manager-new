import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDisplayDate } from '../../../../lib/datetime.js'

export function StitchIcon({ name, filled = false, className = '', style = undefined }) {
  const fillStyle = filled
    ? { fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24", ...style }
    : style
  return (
    <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden="true" style={fillStyle}>
      {name}
    </span>
  )
}

export function StitchWorkspaceSubhead({
  caseCode,
  saving,
  title = 'Observation Builder',
}) {
  return (
    <header className="flex flex-wrap justify-between items-center gap-3 mb-6 pb-4 border-b border-outline-variant/30">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-on-surface-variant m-0">{title}</h2>
        <span className="bg-lush-purple/10 text-lush-purple px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider font-mono">
          Clinical Workspace
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {caseCode ? <span className="text-sm text-on-surface-variant">{caseCode}</span> : null}
        <span className="inline-flex items-center gap-2 bg-surface-container px-4 py-1.5 rounded-full border border-outline-variant/50 text-xs font-semibold font-mono">
          <span className="live-sync-dot" aria-hidden="true" />
          {saving ? 'Saving…' : 'Live Syncing'}
        </span>
      </div>
    </header>
  )
}

export function StitchChipPanel({
  title,
  icon,
  items = [],
  aiSuggestions = [],
  chipTone = 'mint',
  readOnly,
  onChange,
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [draft, setDraft] = useState('')

  function remove(idx) {
    if (readOnly) return
    onChange?.(items.filter((_, i) => i !== idx))
  }

  function accept(label) {
    if (readOnly || !label || items.includes(label)) return
    onChange?.([...items, label])
  }

  function commitAdd() {
    const value = draft.trim()
    if (!value || items.includes(value)) {
      setDraft('')
      setAddOpen(false)
      return
    }
    onChange?.([...items, value])
    setDraft('')
    setAddOpen(false)
  }

  const titleClass = chipTone === 'barrier'
    ? 'text-body-md font-bold text-error mb-4 flex items-center gap-2'
    : 'text-base font-bold text-lush-forest mb-4 flex items-center gap-2'

  const chipClass = chipTone === 'barrier'
    ? 'px-3 py-1.5 rounded-lg bg-error-container/40 text-error text-sm font-bold inline-flex items-center gap-1'
    : chipTone === 'neutral'
      ? 'px-3 py-1.5 rounded-lg bg-surface-container text-on-surface text-sm font-bold inline-flex items-center gap-1'
      : 'px-3 py-1.5 rounded-lg bg-lush-mint/40 text-lush-forest text-sm font-bold inline-flex items-center gap-1'

  return (
    <section className="bg-surface-container-lowest p-6 rounded-xl clinical-shadow border border-outline-variant/30">
      <h3 className={titleClass}>
        <StitchIcon name={icon} />
        {title}
      </h3>
      <div className="flex flex-wrap gap-2">
        {items.map((item, idx) => (
          <span key={`${item}-${idx}`} className={chipClass}>
            {item}
            {!readOnly ? (
              <button type="button" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center border-0 bg-transparent cursor-pointer" onClick={() => remove(idx)} aria-label={`Remove ${item}`}>
                <StitchIcon name="close" className="text-xs" />
              </button>
            ) : null}
          </span>
        ))}
        {aiSuggestions.map((s) => (
          <span key={s} className="px-3 py-1.5 rounded-lg ai-suggestion text-lush-purple text-sm font-bold inline-flex items-center gap-2">
            <StitchIcon name="auto_awesome" className="text-xs" />
            {s}
            {!readOnly ? (
              <button type="button" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center border-0 bg-transparent cursor-pointer text-lush-purple" onClick={() => accept(s)} aria-label={`Add ${s}`}>
                <StitchIcon name="add" className="text-xs" />
              </button>
            ) : null}
          </span>
        ))}
        {!readOnly && addOpen ? (
          <div className="flex flex-wrap items-center gap-2 w-full">
            <input
              type="text"
              className="flex-1 min-w-[140px] px-3 py-2 border border-outline-variant rounded-lg text-sm min-h-[44px]"
              value={draft}
              placeholder={`Add ${title.toLowerCase()}…`}
              autoFocus
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  commitAdd()
                }
                if (e.key === 'Escape') {
                  setAddOpen(false)
                  setDraft('')
                }
              }}
            />
            <button type="button" className="px-4 py-2 rounded-lg bg-lush-forest text-white text-sm font-bold min-h-[44px]" onClick={commitAdd}>
              Add
            </button>
            <button type="button" className="px-3 py-2 rounded-lg border border-outline-variant text-sm min-h-[44px]" onClick={() => { setAddOpen(false); setDraft('') }}>
              Cancel
            </button>
          </div>
        ) : null}
        {!readOnly && !addOpen ? (
          <button
            type="button"
            className="px-3 py-1.5 rounded-lg border border-dashed border-outline text-outline text-sm font-semibold hover:border-lush-forest transition-colors min-h-[44px]"
            onClick={() => setAddOpen(true)}
          >
            + Add Yours
          </button>
        ) : null}
      </div>
    </section>
  )
}

export function StitchChildSnapshot({
  childName,
  caseCode,
  assessorName,
  snapshotText,
  summaryText,
  readOnly,
  onSnapshotBlur,
  onSummaryBlur,
}) {
  return (
    <section className="bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
      <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
        <div className="flex gap-6">
          <div className="w-20 h-20 rounded-2xl bg-lush-mint/30 flex items-center justify-center shrink-0">
            <StitchIcon name="face" filled className="text-4xl text-lush-forest" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-lush-forest m-0">{childName || 'Client'}</h2>
            {caseCode ? (
              <div className="flex gap-4 text-on-surface-variant mt-1">
                <span className="flex items-center gap-1 text-xs font-mono font-medium">
                  <StitchIcon name="tag" className="text-sm" />
                  {caseCode}
                </span>
              </div>
            ) : null}
          </div>
        </div>
        {assessorName ? (
          <div className="text-right">
            <p className="text-xs font-bold uppercase text-outline font-mono m-0">Assessor</p>
            <p className="text-base font-bold m-0">{assessorName}</p>
          </div>
        ) : null}
      </div>
      <div className="pt-6 border-t border-outline-variant/30">
        <h3 className="text-xs font-bold uppercase text-lush-forest mb-3 flex items-center gap-2 font-mono m-0">
          <StitchIcon name="summarize" className="text-sm" />
          Case Summary
        </h3>
        <textarea
          className="w-full bg-transparent border-none p-0 text-base leading-relaxed text-on-surface focus:ring-0 min-h-[100px] resize-y"
          placeholder="Enter high-level clinical summary of this observation cycle…"
          defaultValue={summaryText || ''}
          disabled={readOnly}
          onBlur={(e) => onSummaryBlur?.(e.target.value)}
        />
      </div>
      <div className="mt-6">
        <h3 className="text-xs font-bold uppercase text-outline mb-3 font-mono m-0">Child snapshot</h3>
        <textarea
          className="w-full bg-transparent border-none p-0 text-base leading-relaxed text-on-surface focus:ring-0 min-h-[80px] resize-y"
          placeholder="Brief strengths-forward snapshot…"
          defaultValue={snapshotText || ''}
          disabled={readOnly}
          onBlur={(e) => onSnapshotBlur?.(e.target.value)}
        />
      </div>
    </section>
  )
}

export function StitchEvidenceInsights({
  evidence,
  readOnly,
  logsPath,
  documentsPath,
  evidenceUpload,
}) {
  const sources = evidence?.sources || []

  function sourceHref(key) {
    if (key === 'session_logs') return logsPath
    if (key === 'uploads') return documentsPath
    if (key === 'parent_inputs' || key === 'school_inputs') return '#stakeholder-inputs'
    return documentsPath
  }

  return (
    <section className="bg-surface-container-lowest rounded-xl clinical-shadow border border-outline-variant/30 overflow-hidden">
      <div className="p-6 border-b border-outline-variant/30 bg-surface-container-lowest">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <StitchIcon name="inventory_2" className="text-lush-forest" />
            <div>
              <h3 className="text-2xl font-bold text-lush-forest m-0">Clinical Evidence</h3>
              <p className="text-sm text-on-surface-variant m-0 mt-1">
                Tap a source to open session logs, uploads, or stakeholder inputs.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="p-6 grid grid-cols-2 lg:grid-cols-4 gap-4">
        {(sources.length ? sources : [
          { key: 'session_logs', label: 'Session logs', count: evidence?.session_logs ?? 0, detail: `${evidence?.logs_with_notes ?? 0} with notes`, icon: 'event_note' },
          { key: 'uploads', label: 'Uploaded files', count: evidence?.evidence_uploads ?? 0, detail: 'Photos, PDFs, video', icon: 'folder_open' },
          { key: 'parent_inputs', label: 'Parent inputs', count: evidence?.parent_inputs ?? 0, detail: 'Family observations', icon: 'family_restroom' },
          { key: 'school_inputs', label: 'School inputs', count: evidence?.school_inputs ?? 0, detail: 'School team notes', icon: 'school' },
        ]).map((source) => {
          const href = sourceHref(source.key)
          const inner = (
            <>
              <div className="flex items-center gap-2">
                <StitchIcon name={source.icon || 'description'} className="text-lush-forest text-[20px]" />
                <p className="text-[10px] font-bold uppercase text-outline m-0 font-mono">{source.label}</p>
              </div>
              <p className="text-2xl font-bold text-lush-forest m-0">{source.count ?? 0}</p>
              <p className="text-xs text-on-surface-variant m-0">{source.detail}</p>
              {href ? (
                <span className="text-[10px] font-bold text-lush-forest mt-auto inline-flex items-center gap-1">
                  Open
                  <StitchIcon name="arrow_forward" className="text-sm" />
                </span>
              ) : null}
            </>
          )
          return href && href.startsWith('#') ? (
            <a
              key={source.key}
              href={href}
              className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-2 min-h-[110px] hover:border-lush-forest hover:bg-lush-mint/10 transition-all no-underline text-inherit"
            >
              {inner}
            </a>
          ) : href ? (
            <Link
              key={source.key}
              to={href}
              className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-2 min-h-[110px] hover:border-lush-forest hover:bg-lush-mint/10 transition-all no-underline text-inherit"
            >
              {inner}
            </Link>
          ) : (
            <div key={source.key} className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-2 min-h-[110px]">
              {inner}
            </div>
          )
        })}
      </div>

      <div className="px-6 pb-6 border-t border-outline-variant/20 pt-6">
        <div className="flex justify-between items-center mb-4">
          <h4 className="text-base font-bold m-0">Evidence Drive</h4>
          <span className="text-xs text-on-surface-variant font-mono">Stored in document drive · visible to CM on review</span>
        </div>
        {evidenceUpload || null}
      </div>
    </section>
  )
}

export function StitchEnvironmentsSection({ environments = [], readOnly, onChange }) {
  const presets = ['Playground', 'Peer Relationships', 'Classroom', 'Home']

  function updateNotes(idx, notes) {
    onChange?.(environments.map((e, i) => (i === idx ? { ...e, notes } : e)))
  }

  function remove(idx) {
    onChange?.(environments.filter((_, i) => i !== idx))
  }

  function addPreset(label) {
    if (environments.some((e) => e.label === label)) return
    onChange?.([...environments, { key: `env_${Date.now()}`, label, notes: '' }])
  }

  return (
    <section className="bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
      <h3 className="text-2xl font-bold text-lush-forest flex items-center gap-2 mb-6 m-0">
        <StitchIcon name="location_on" />
        Environments Workspace
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {environments.map((env, idx) => (
          <div key={env.key || idx} className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/30">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <StitchIcon name={env.label?.toLowerCase().includes('home') ? 'home' : 'school'} className="text-lush-forest" />
                <h4 className="font-bold text-lush-forest m-0">{env.label}</h4>
              </div>
              {!readOnly ? (
                <button type="button" className="min-h-[44px] min-w-[44px] border-0 bg-transparent cursor-pointer text-outline" onClick={() => remove(idx)} aria-label={`Remove ${env.label}`}>
                  <StitchIcon name="close" className="text-sm" />
                </button>
              ) : null}
            </div>
            <textarea
              className="w-full bg-transparent border-none p-0 text-sm focus:ring-0 min-h-[80px] resize-y"
              placeholder={`Observations from ${env.label?.toLowerCase() || 'environment'}…`}
              defaultValue={env.notes || ''}
              disabled={readOnly}
              onBlur={(e) => updateNotes(idx, e.target.value)}
            />
          </div>
        ))}
      </div>
      {!readOnly ? (
        <div className="mt-6 flex flex-wrap gap-2">
          <span className="text-xs font-bold uppercase text-outline w-full mb-2 font-mono">Add Environment</span>
          {presets.filter((p) => !environments.some((e) => e.label === p)).map((p) => (
            <button key={p} type="button" className="px-3 py-1.5 rounded-lg border border-outline text-outline text-xs font-bold hover:border-lush-forest hover:text-lush-forest transition-colors min-h-[44px]" onClick={() => addPreset(p)}>
              {p}
            </button>
          ))}
          <button
            type="button"
            className="px-3 py-1.5 rounded-lg border border-dashed border-outline text-outline text-xs font-bold hover:border-lush-forest transition-colors min-h-[44px]"
            onClick={() => {
              const label = window.prompt('Environment name')
              if (label?.trim()) addPreset(label.trim())
            }}
          >
            + Add Other
          </button>
        </div>
      ) : null}
    </section>
  )
}

export function StitchGoalsSection({
  goals = [],
  pendingGoals = [],
  strategies = [],
  readOnly,
  onAddCandidate,
  onAddGoalStrategy,
}) {
  return (
    <section className="bg-surface-container-lowest p-5 sm:p-8 rounded-xl clinical-shadow border border-outline-variant/30">
      <h3 className="text-xl sm:text-2xl font-bold text-lush-forest mb-2 m-0">Goals &amp; Strategies</h3>
      <p className="text-sm text-on-surface-variant mb-6 m-0">
        Recommended from session logs and concerns. Added items appear here and route to case manager review.
      </p>
      <div className="space-y-4">
        {goals.length ? (
          <div>
            <p className="text-xs font-bold uppercase text-lush-purple mb-3 font-mono m-0 flex items-center gap-1">
              <StitchIcon name="auto_awesome" className="text-sm" />
              Recommended
            </p>
            {goals.map((g, idx) => (
              <StitchGoalRow
                key={g.id || `${g.label}-${idx}`}
                goal={g}
                index={idx + 1}
                variant="recommended"
                readOnly={readOnly}
                onAddCandidate={onAddCandidate}
                onAddGoalStrategy={onAddGoalStrategy}
              />
            ))}
          </div>
        ) : null}
        {pendingGoals.length ? (
          <div>
            <p className="text-xs font-bold uppercase text-outline mb-3 font-mono m-0">Added goals</p>
            {pendingGoals.map((g) => (
              <StitchGoalRow
                key={g.id}
                goal={g}
                index="✓"
                variant="pending"
                readOnly={readOnly}
                onAddGoalStrategy={onAddGoalStrategy}
              />
            ))}
          </div>
        ) : null}
        {strategies.length ? (
          <div>
            <p className="text-xs font-bold uppercase text-outline mb-3 font-mono m-0">Added strategies</p>
            <div className="space-y-2">
              {strategies.map((s) => (
                <div key={s.id} className="flex items-center justify-between p-3 bg-surface-container rounded-lg border border-outline-variant/30 gap-2">
                  <span className="font-semibold text-sm">{s.label}</span>
                  <span className="text-[10px] uppercase font-bold text-outline px-2 py-0.5 border border-outline-variant rounded-full font-mono">{s.status || 'Strategy'}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {!readOnly ? (
          <button
            type="button"
            className="w-full py-3 border-2 border-dashed border-lush-forest text-lush-forest rounded-xl font-bold hover:bg-lush-mint/10 transition-all flex items-center justify-center gap-2 min-h-[44px]"
            onClick={onAddGoalStrategy}
          >
            <StitchIcon name="add" />
            Add goal &amp; strategy
          </button>
        ) : null}
      </div>
    </section>
  )
}

export function StitchStrategiesSection({
  strategies = [],
  aiMatches = [],
  readOnly,
  strategyDraft,
  onDraftChange,
  onAddStrategy,
  onAcceptMatch,
}) {
  return (
    <section className="bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
      <h3 className="text-2xl font-bold text-lush-forest flex items-center gap-2 mb-6 m-0">
        <StitchIcon name="lightbulb" />
        Strategies Workspace
      </h3>
      <div className="space-y-6">
        <div>
          <p className="text-xs font-bold uppercase text-outline mb-3 font-mono m-0">Currently Using</p>
          <div className="space-y-2">
            {strategies.length ? strategies.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-3 bg-surface-container rounded-lg border border-outline-variant/30 gap-2">
                <span className="font-semibold text-sm">{s.label}</span>
                <span className="text-[10px] uppercase font-bold text-outline px-2 py-0.5 border border-outline-variant rounded-full font-mono">{s.domain_key || 'Strategy'}</span>
              </div>
            )) : (
              <p className="text-sm text-on-surface-variant m-0">No strategies added yet.</p>
            )}
          </div>
        </div>
        {aiMatches.length ? (
          <div>
            <p className="text-xs font-bold uppercase text-lush-purple mb-3 flex items-center gap-1 font-mono m-0">
              <StitchIcon name="auto_awesome" className="text-sm" />
              Suggested
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {aiMatches.map((m) => (
                <div key={m.id || m.label} className="p-3 ai-suggestion rounded-lg flex items-center justify-between gap-2">
                  <span className="text-sm font-bold">{m.label}</span>
                  {!readOnly ? (
                    <button type="button" className="text-lush-purple min-h-[44px] min-w-[44px] border-0 bg-transparent cursor-pointer" onClick={() => onAcceptMatch?.(m.label)} aria-label={`Add ${m.label}`}>
                      <StitchIcon name="add_circle" className="text-sm" />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {!readOnly ? (
          <>
            <input
              className="w-full px-3 py-2 border border-outline-variant rounded-lg text-sm min-h-[44px]"
              value={strategyDraft}
              onChange={(e) => onDraftChange?.(e.target.value)}
              placeholder="Search or add strategy…"
            />
            <button type="button" className="w-full py-3 border-2 border-dashed border-outline-variant text-outline rounded-xl font-bold hover:border-lush-forest hover:text-lush-forest transition-all flex items-center justify-center gap-2 min-h-[44px]" onClick={onAddStrategy}>
              <StitchIcon name="add" />
              Add Your Own Strategy
            </button>
          </>
        ) : null}
      </div>
    </section>
  )
}

export function StitchStakeholderInputs({ sections, readOnly, onBlur }) {
  const fields = [
    { key: 'parent_inputs', label: 'Parent Inputs' },
    { key: 'school_inputs', label: 'School Inputs' },
    { key: 'internal_notes', label: 'Mentor/CM Inputs' },
    { key: 'clinical_summary', label: 'Therapist Concerns' },
  ]

  return (
    <section id="stakeholder-inputs" className="bg-surface-container-lowest p-5 sm:p-8 rounded-xl clinical-shadow border border-outline-variant/30 scroll-mt-24">
      <h3 className="text-xl sm:text-2xl font-bold text-lush-forest mb-6 m-0">Stakeholder Inputs</h3>
      <div className="space-y-6">
        {fields.map(({ key, label }) => {
          const sec = sections.find((s) => s.key === key) || {}
          return (
            <div key={key}>
              <label className="text-xs font-bold uppercase text-outline mb-2 block font-mono" htmlFor={`ob-stake-${key}`}>{label}</label>
              <textarea
                id={`ob-stake-${key}`}
                className="w-full border border-outline-variant rounded-xl p-4 text-sm focus:ring-lush-mint min-h-[80px] resize-y"
                placeholder={`Summary for ${label.toLowerCase()}…`}
                defaultValue={sec.narrative_text || ''}
                disabled={readOnly}
                onBlur={(e) => onBlur?.(key, e.target.value)}
              />
            </div>
          )
        })}
      </div>
    </section>
  )
}

function sectionCheckIcon(status) {
  if (status === 'completed') {
    return { name: 'check_circle', filled: true, className: 'text-emerald-600 shrink-0' }
  }
  if (status === 'in_progress') {
    return { name: 'pending', filled: false, className: 'text-amber-500 shrink-0' }
  }
  return { name: 'cancel', filled: false, className: 'text-red-500 shrink-0' }
}

export function StitchSectionChecklist({ items }) {
  if (!items?.length) return null
  const doneCount = items.filter((item) => item.status === 'completed').length
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <p className="text-xs font-bold uppercase text-outline font-mono m-0">Report progress</p>
        <span className="text-[10px] font-mono text-on-surface-variant">{doneCount}/{items.length}</span>
      </div>
      <ul className="ob-ai-rail__checklist m-0 p-0 list-none space-y-2">
        {items.map((item) => {
          const icon = sectionCheckIcon(item.status)
          const done = item.status === 'completed'
          return (
            <li
              key={item.key}
              className={`ob-checklist-item flex items-start gap-2 rounded-lg px-2 py-1.5 transition-colors ${
                done ? 'bg-emerald-50/80' : item.status === 'not_started' ? 'bg-red-50/60' : 'bg-amber-50/60'
              }`}
            >
              <StitchIcon name={icon.name} filled={icon.filled} className={`text-[18px] mt-0.5 ${icon.className}`} />
              <span className={`text-sm leading-snug ${done ? 'text-emerald-900 font-medium' : 'text-on-surface-variant'}`}>
                {item.label}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function StitchBuilderRail({
  completionPct,
  updatedAt,
  sectionChecklist,
  insights,
  smartAction,
  onPreview,
  onClose,
  onGenerateInsights,
  generatingInsights,
  onApplyInsights,
  applyingInsights,
  onSaveDraft,
  savingDraft,
  draftSavedFlash,
  readOnly,
}) {
  return (
    <aside className="ob-ai-rail w-full lg:w-80 shrink-0">
      <div className="ob-ai-rail__sticky space-y-4">
        <div className="bg-surface-container-lowest p-6 rounded-xl clinical-shadow border border-ai-accent/20">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div className="flex items-center gap-2 min-w-0">
              <StitchIcon name="psychology" className="text-lush-purple shrink-0" />
              <h4 className="font-bold text-base text-on-surface m-0">Suggested supports</h4>
            </div>
            {onClose ? (
              <button
                type="button"
                className="shrink-0 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg border border-outline-variant/50 bg-surface-container-low text-outline hover:text-lush-forest hover:border-lush-forest transition-colors"
                onClick={onClose}
                aria-label="Hide suggested supports"
              >
                <StitchIcon name="close" className="text-lg" />
              </button>
            ) : null}
          </div>
          {!readOnly && onGenerateInsights ? (
            <button
              type="button"
              className="w-full mb-4 min-h-[44px] px-4 py-2.5 rounded-xl bg-lush-purple text-white font-bold text-sm flex items-center justify-center gap-2 shadow-sm hover:opacity-90 transition-all disabled:opacity-60"
              disabled={generatingInsights}
              onClick={onGenerateInsights}
            >
              <StitchIcon name="auto_awesome" className="text-[18px]" />
              {generatingInsights ? 'Generating insights…' : 'Generate Session Insights'}
            </button>
          ) : null}
          {insights?.summary ? (
            <div className="mt-4 p-4 rounded-xl ai-suggestion border-lush-purple/30">
              <p className="text-xs font-bold uppercase text-lush-purple mb-2 font-mono m-0">Session insights</p>
              <p className="text-sm text-lush-purple/90 m-0 leading-snug">{insights.summary}</p>
              {insights.patterns?.length ? (
                <ul className="m-0 mt-3 p-0 list-none space-y-2">
                  {insights.patterns.map((pattern) => (
                    <li key={pattern.key || pattern.label} className="text-xs text-on-surface-variant flex items-start gap-2">
                      <StitchIcon name="insights" className="text-lush-purple text-[16px] shrink-0 mt-0.5" />
                      <span><strong className="text-on-surface">{pattern.label}:</strong> {pattern.value}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {insights?.field_suggestions && Object.keys(insights.field_suggestions).length ? (
            <div className="mt-4 p-4 rounded-xl border border-outline-variant/30 bg-surface-container-low">
              <p className="text-xs font-bold uppercase text-outline mb-2 font-mono m-0">Draft preview from logs</p>
              <ul className="m-0 p-0 list-none space-y-2 max-h-40 overflow-y-auto">
                {Object.entries(insights.field_suggestions).map(([key, value]) => (
                  <li key={key} className="text-xs text-on-surface-variant">
                    <strong className="text-on-surface font-mono">{key.replace(/_/g, ' ')}</strong>
                    {typeof value === 'string' ? `: ${value.slice(0, 100)}${value.length > 100 ? '…' : ''}` : ' · structured chips'}
                  </li>
                ))}
              </ul>
              {!readOnly && onApplyInsights ? (
                <button
                  type="button"
                  className="w-full mt-3 min-h-[44px] px-4 py-2 rounded-xl border-2 border-lush-forest text-lush-forest font-bold text-sm hover:bg-lush-mint/10 disabled:opacity-50"
                  disabled={applyingInsights}
                  onClick={onApplyInsights}
                >
                  {applyingInsights ? 'Applying…' : 'Apply insights to report'}
                </button>
              ) : null}
            </div>
          ) : null}
          <div className={insights?.summary || (!readOnly && onGenerateInsights) ? 'mt-5' : ''}>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-outline uppercase font-mono">Draft completeness</span>
              <span className="text-lush-forest font-bold">{completionPct ?? 0}%</span>
            </div>
            <div className="w-full h-2 bg-surface-container rounded-full overflow-hidden">
              <div className="h-full bg-lush-forest rounded-full transition-[width] duration-300" style={{ width: `${completionPct ?? 0}%` }} />
            </div>
            {updatedAt ? (
              <p className="text-sm text-on-surface-variant mt-3 m-0">Last saved {formatDisplayDate(updatedAt.slice(0, 10))}</p>
            ) : null}
          </div>
          {smartAction ? (
            <div className="p-4 bg-lush-purple/5 border border-lush-purple/10 rounded-xl mt-5">
              <p className="text-xs font-bold text-lush-purple uppercase mb-2 font-mono m-0">Smart action</p>
              <p className="text-sm text-on-surface-variant leading-snug m-0">{smartAction}</p>
            </div>
          ) : null}
          <StitchSectionChecklist items={sectionChecklist} />
          {!readOnly && onSaveDraft ? (
            <div className="mt-5 pt-4 border-t border-outline-variant/30">
              <button
                type="button"
                className="w-full min-h-[44px] px-4 py-2.5 rounded-xl bg-lush-forest text-white font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-all disabled:opacity-50"
                disabled={savingDraft}
                onClick={onSaveDraft}
              >
                <StitchIcon name="save" className="text-[18px]" />
                {savingDraft ? 'Saving draft…' : 'Save draft'}
              </button>
              {draftSavedFlash ? (
                <p className="text-xs text-emerald-700 font-medium text-center mt-2 m-0">Draft saved</p>
              ) : (
                <p className="text-[10px] text-outline text-center mt-2 m-0 font-mono">Auto-saves every 5 minutes</p>
              )}
            </div>
          ) : null}
        </div>
        <div className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30">
          <h4 className="font-bold text-sm mb-3 m-0 text-on-surface-variant uppercase tracking-wide font-mono">Quick actions</h4>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" className="p-3 bg-surface-container-low rounded-lg flex flex-col items-center gap-1 hover:bg-lush-mint/10 transition-all min-h-[44px] border-0 cursor-pointer" onClick={onPreview}>
              <StitchIcon name="print" className="text-outline" />
              <span className="text-[10px] font-bold">Print draft</span>
            </button>
            <button type="button" className="p-3 bg-surface-container-low rounded-lg flex flex-col items-center gap-1 hover:bg-lush-mint/10 transition-all min-h-[44px] border-0 cursor-pointer" onClick={onPreview}>
              <StitchIcon name="history_edu" className="text-outline" />
              <span className="text-[10px] font-bold">Preview</span>
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}

export function StitchBuilderFooter({ saving, canSubmit, readOnly, lastSaved, onPreview, onSubmit }) {
  return (
    <footer className="sticky bottom-0 z-20 mt-8 -mx-1 px-4 sm:px-6 py-3 sm:py-4 bg-surface-container-lowest border-t border-outline-variant/30 sticky-footer flex flex-col sm:flex-row sm:flex-wrap justify-between items-stretch sm:items-center gap-3 sm:gap-4 ob-sticky-footer">
      <span className="text-xs text-outline font-bold italic font-mono m-0 text-center sm:text-left">
        {saving ? 'Saving…' : lastSaved ? `Last saved: ${lastSaved}` : 'Auto-saves every 5 minutes while you work'}
      </span>
      <div className="flex flex-col xs:flex-row flex-wrap gap-2 sm:gap-4 justify-stretch sm:justify-end w-full sm:w-auto">
        <button type="button" className="w-full sm:w-auto px-6 sm:px-8 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold hover:bg-lush-mint/10 transition-all min-h-[44px]" onClick={onPreview}>
          Preview Report
        </button>
        {!readOnly ? (
          <button type="button" className="w-full sm:w-auto px-6 sm:px-8 py-3 rounded-xl bg-lush-forest text-white font-bold shadow-lg hover:opacity-90 transition-all flex items-center justify-center gap-2 min-h-[44px] disabled:opacity-50" disabled={!canSubmit || saving} onClick={onSubmit}>
            <StitchIcon name="send" />
            Finalize &amp; Submit
          </button>
        ) : null}
      </div>
    </footer>
  )
}

function StitchGoalRow({
  goal,
  index,
  variant = 'recommended',
  readOnly,
  onAddCandidate,
  onAddGoalStrategy,
}) {
  const [expanded, setExpanded] = useState(false)
  const detail = goal.description || goal.goal_statement || goal.baseline_note || goal.baseline || ''
  const hasDetail = Boolean(detail && detail !== goal.label)
  const badgeClass = variant === 'recommended'
    ? 'w-10 h-10 rounded-full bg-lush-purple/10 flex items-center justify-center font-bold text-lush-purple shrink-0'
    : 'w-10 h-10 rounded-full bg-lush-mint/50 flex items-center justify-center font-bold text-lush-forest shrink-0'

  return (
    <div className="ob-goal-row p-4 bg-surface-container-low rounded-xl border border-outline-variant/30 mb-2">
      <div className="flex items-start gap-3 sm:gap-4">
        <div className={badgeClass}>{index}</div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-sm m-0 break-words">{goal.label}</p>
          {!expanded && hasDetail ? (
            <p className="text-xs text-on-surface-variant m-0 mt-0.5 line-clamp-2">{detail}</p>
          ) : null}
          {variant === 'pending' ? (
            <p className="text-xs text-on-surface-variant m-0 mt-0.5">Under case manager review</p>
          ) : null}
          {goal.source === 'session_log' ? (
            <span className="text-[10px] uppercase font-mono text-lush-forest">From session log</span>
          ) : null}
        </div>
        {hasDetail ? (
          <button
            type="button"
            className="shrink-0 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg border border-outline-variant/50 bg-surface-container-low text-lush-forest"
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse goal details' : 'Expand goal details'}
            onClick={() => setExpanded((open) => !open)}
          >
            <StitchIcon name={expanded ? 'remove' : 'add'} />
          </button>
        ) : null}
        {!readOnly && variant === 'recommended' && !expanded ? (
          <button
            type="button"
            className="ob-goal-row__cta bg-lush-forest text-white px-4 py-2 rounded-lg text-sm font-bold min-h-[44px] shrink-0 hidden sm:inline-flex"
            onClick={() => onAddCandidate?.(goal.label)}
          >
            Add goal
          </button>
        ) : null}
      </div>
      {expanded ? (
        <div className="mt-3 pt-3 border-t border-outline-variant/30 space-y-3">
          {hasDetail ? <p className="text-sm text-on-surface-variant m-0 leading-relaxed">{detail}</p> : null}
          {!readOnly ? (
            <div className="flex flex-col sm:flex-row flex-wrap gap-2">
              {variant === 'recommended' ? (
                <button
                  type="button"
                  className="w-full sm:w-auto bg-lush-forest text-white px-4 py-2 rounded-lg text-sm font-bold min-h-[44px]"
                  onClick={() => onAddCandidate?.(goal.label)}
                >
                  Add goal
                </button>
              ) : null}
              <button
                type="button"
                className="w-full sm:w-auto px-4 py-2 rounded-lg border-2 border-dashed border-lush-forest text-lush-forest text-sm font-bold min-h-[44px]"
                onClick={onAddGoalStrategy}
              >
                Add goal &amp; strategy
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

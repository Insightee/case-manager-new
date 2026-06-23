import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { useObservationReport } from '../hooks/useObservationReport.js'
import { StudentGoalCreateModal } from '../../clinical/goals-strategy/StudentGoalCreateModal.jsx'
import { ObservationEvidenceUpload } from './ObservationEvidenceUpload.jsx'
import {
  StitchBuilderFooter,
  StitchBuilderRail,
  StitchChildSnapshot,
  StitchChipPanel,
  StitchEnvironmentsSection,
  StitchEvidenceInsights,
  StitchGoalsSection,
  StitchStakeholderInputs,
  StitchWorkspaceSubhead,
} from './stitch/ObservationStitchBlocks.jsx'

function sectionByKey(sections, key) {
  return sections?.find((s) => s.key === key) || {}
}

export function ObservationBuilderPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const {
    workspace,
    evidence,
    candidates,
    insights,
    loading,
    error,
    saving,
    loadWorkspace,
    patchSection,
    submitReport,
    generateInsights,
    applyInsights,
    reloadEvidence,
    addGoalCandidate,
    saveDraft,
    AUTO_SAVE_MS,
  } = useObservationReport(caseId)

  const [aiAssistantOpen, setAiAssistantOpen] = useState(false)
  const [draftSavedFlash, setDraftSavedFlash] = useState(false)
  const [generatingInsights, setGeneratingInsights] = useState(false)
  const [goalModalOpen, setGoalModalOpen] = useState(false)

  const flushPendingEdits = useCallback(() => {
    const root = document.querySelector('.observation-workspace')
    const active = document.activeElement
    if (root && active && root.contains(active) && typeof active.blur === 'function') {
      active.blur()
    }
  }, [])

  const handleSaveDraft = useCallback(async () => {
    const result = await saveDraft(flushPendingEdits)
    if (result) {
      setDraftSavedFlash(true)
      window.setTimeout(() => setDraftSavedFlash(false), 3000)
    }
  }, [saveDraft, flushPendingEdits])

  const handleGenerateInsights = useCallback(async () => {
    setGeneratingInsights(true)
    try {
      await generateInsights()
    } finally {
      setGeneratingInsights(false)
    }
  }, [generateInsights])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  const sections = workspace?.sections || []
  const readOnly = !workspace?.can_edit

  useEffect(() => {
    if (!workspace?.report_id || readOnly) return undefined
    const timer = window.setInterval(() => {
      saveDraft(flushPendingEdits)
    }, AUTO_SAVE_MS)
    return () => window.clearInterval(timer)
  }, [workspace?.report_id, readOnly, saveDraft, flushPendingEdits, AUTO_SAVE_MS])

  const strengthsSec = sectionByKey(sections, 'strengths_interests')
  const supportSec = sectionByKey(sections, 'support_needs')
  const envSec = sectionByKey(sections, 'environment_notes')
  const chipData = strengthsSec.structured_data || {}
  const supportData = supportSec.structured_data || {}
  const envData = envSec.structured_data || { environments: [] }
  const suggestedTiles = insights?.suggested_tiles || {}

  const smartAction = useMemo(() => {
    const first = insights?.patterns?.[0]
    if (!first) return null
    return `"Session logs highlight ${first.label.toLowerCase()}. Consider documenting related supports in strategies or environments."`
  }, [insights])

  const sectionChecklist = useMemo(() => {
    const catalog = workspace?.section_catalog || []
    const byKey = Object.fromEntries((workspace?.sections || []).map((s) => [s.key, s]))
    return catalog
      .filter((m) => m.required)
      .map((m) => ({
        key: m.key,
        label: m.label,
        status: byKey[m.key]?.completion_status || 'not_started',
      }))
  }, [workspace])

  async function saveChips(sectionKey, data) {
    await patchSection(sectionKey, { structured_data: data })
  }

  async function refreshCandidates() {
    await loadWorkspace()
  }

  if (loading && !workspace) {
    return <p className="text-sm text-on-surface-variant m-0">Loading builder…</p>
  }

  return (
    <>
      <StitchWorkspaceSubhead
        caseCode={caseCode}
        saving={saving}
        aiAssistantOpen={aiAssistantOpen}
        onToggleAiAssistant={() => setAiAssistantOpen((open) => !open)}
        completionPct={workspace?.completion_pct ?? 0}
      />

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}
      {workspace?.reviewer_comment && workspace?.status === 'returned_for_changes' ? (
        <p className="mb-4 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-sm"><strong>Case manager note:</strong> {workspace.reviewer_comment}</p>
      ) : null}

      <div
        className={`ob-builder-layout flex gap-6 sm:gap-8 pb-24 sm:pb-8 ${
          aiAssistantOpen ? 'ob-builder-layout--split flex-col lg:flex-row lg:items-start' : 'ob-builder-layout--expanded flex-col'
        }`}
      >
        <div className="flex-1 space-y-8 min-w-0 w-full">
          <StitchChildSnapshot
            childName={childName}
            caseCode={caseCode}
            snapshotText={sectionByKey(sections, 'child_snapshot').narrative_text}
            summaryText={sectionByKey(sections, 'referral_background').narrative_text}
            readOnly={readOnly}
            onSnapshotBlur={(v) => patchSection('child_snapshot', { narrative_text: v })}
            onSummaryBlur={(v) => patchSection('referral_background', { narrative_text: v })}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <StitchChipPanel
              title="Strengths"
              icon="stars"
              items={chipData.strengths || []}
              aiSuggestions={suggestedTiles.strengths || []}
              readOnly={readOnly}
              onChange={(items) => saveChips('strengths_interests', { ...chipData, strengths: items })}
            />
            <StitchChipPanel
              title="Interests"
              icon="favorite"
              items={chipData.interests || []}
              aiSuggestions={suggestedTiles.interests || []}
              readOnly={readOnly}
              onChange={(items) => saveChips('strengths_interests', { ...chipData, interests: items })}
            />
            <StitchChipPanel
              title="Support Needs"
              icon="psychology_alt"
              items={supportData.support_needs || []}
              aiSuggestions={suggestedTiles.support_needs || []}
              chipTone="neutral"
              readOnly={readOnly}
              onChange={(items) => saveChips('support_needs', { ...supportData, support_needs: items })}
            />
            <StitchChipPanel
              title="Access Barriers"
              icon="block"
              items={supportData.barriers || []}
              aiSuggestions={suggestedTiles.barriers || []}
              chipTone="barrier"
              readOnly={readOnly}
              onChange={(items) => saveChips('support_needs', { ...supportData, barriers: items })}
            />
          </div>

          <StitchEvidenceInsights
            evidence={evidence}
            readOnly={readOnly}
            logsPath={`${basePath}?tab=logs`}
            documentsPath={`${basePath}?tab=documents`}
            evidenceUpload={(
              <ObservationEvidenceUpload
                caseId={caseId}
                reportId={workspace?.report_id}
                readOnly={readOnly}
                onUploaded={reloadEvidence}
              />
            )}
          />

          <StitchEnvironmentsSection
            environments={envData.environments || []}
            readOnly={readOnly}
            onChange={(envs) => saveChips('environment_notes', { environments: envs })}
          />

          <StitchGoalsSection
            goals={candidates.suggested_goals || []}
            pendingGoals={candidates.goals || []}
            strategies={candidates.strategies || []}
            readOnly={readOnly}
            onAddCandidate={async (label) => {
              await addGoalCandidate(label)
              await refreshCandidates()
            }}
            onAddGoalStrategy={() => setGoalModalOpen(true)}
          />

          {goalModalOpen ? (
            <StudentGoalCreateModal
              caseId={caseId}
              clinicalReportId={workspace?.report_id}
              reportType="observation"
              childName={childName || caseCode || 'Student'}
              onClose={() => setGoalModalOpen(false)}
              onCreated={async () => {
                setGoalModalOpen(false)
                await refreshCandidates()
              }}
            />
          ) : null}

          <section className="bg-surface-container-lowest p-5 sm:p-8 rounded-xl clinical-shadow border border-outline-variant/30">
            <h3 className="text-xl sm:text-2xl font-bold text-lush-forest mb-6 m-0">Clinical Domains</h3>
            <div className="space-y-4">
              {['communication', 'regulation_sensory', 'participation', 'learning_access', 'peer_interaction'].map((key) => {
                const sec = sectionByKey(sections, key)
                return (
                  <div key={key}>
                    <label className="text-xs font-bold uppercase text-outline mb-2 block font-mono" htmlFor={`ob-domain-${key}`}>{sec.label || key}</label>
                    <textarea
                      id={`ob-domain-${key}`}
                      className="w-full border border-outline-variant rounded-xl p-4 text-sm focus:ring-lush-mint min-h-[64px] resize-y"
                      rows={2}
                      disabled={readOnly}
                      defaultValue={sec.narrative_text || ''}
                      onBlur={(e) => patchSection(key, { narrative_text: e.target.value })}
                    />
                  </div>
                )
              })}
            </div>
          </section>

          <StitchStakeholderInputs
            sections={sections}
            readOnly={readOnly}
            onBlur={(key, value) => patchSection(key, { narrative_text: value })}
          />

          <section className="bg-surface-container-lowest p-5 sm:p-8 rounded-xl clinical-shadow border border-outline-variant/30">
            <h3 className="text-xl sm:text-2xl font-bold text-lush-forest mb-6 m-0">Clinical Summary &amp; IEP Recommendations</h3>
            {['clinical_summary', 'recommendations_iep'].map((key) => {
              const sec = sectionByKey(sections, key)
              return (
                <div key={key} className="mb-4 last:mb-0">
                  <label className="text-xs font-bold uppercase text-outline mb-2 block font-mono" htmlFor={`ob-sum-${key}`}>{sec.label || key}</label>
                  <textarea
                    id={`ob-sum-${key}`}
                    className="w-full border border-outline-variant rounded-xl p-4 text-sm focus:ring-lush-mint min-h-[120px] resize-y"
                    rows={4}
                    disabled={readOnly}
                    defaultValue={sec.narrative_text || ''}
                    onBlur={(e) => patchSection(key, { narrative_text: e.target.value })}
                  />
                </div>
              )
            })}
          </section>
        </div>

        {aiAssistantOpen ? (
          <StitchBuilderRail
            completionPct={workspace?.completion_pct ?? 0}
            updatedAt={workspace?.updated_at}
            sectionChecklist={sectionChecklist}
            insights={insights}
            smartAction={smartAction}
            readOnly={readOnly}
            generatingInsights={generatingInsights || saving}
            onGenerateInsights={handleGenerateInsights}
            onApplyInsights={applyInsights}
            applyingInsights={saving}
            onSaveDraft={handleSaveDraft}
            savingDraft={saving}
            draftSavedFlash={draftSavedFlash}
            onPreview={() => navigate(`${basePath}?tab=reports&section=observation&view=preview`)}
            onClose={() => setAiAssistantOpen(false)}
          />
        ) : null}
      </div>

      <StitchBuilderFooter
        saving={saving}
        canSubmit={workspace?.can_submit}
        readOnly={readOnly}
        lastSaved={workspace?.updated_at ? formatDisplayDate(workspace.updated_at.slice(0, 10)) : null}
        onPreview={() => navigate(`${basePath}?tab=reports&section=observation&view=preview`)}
        onSubmit={async () => {
          await submitReport()
          navigate(`${basePath}?tab=reports&section=observation`)
        }}
      />
    </>
  )
}

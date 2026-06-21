import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { currentMonthValue, monthOptions } from '../../lib/insightsConstants.js'
import { InsightsTabHeader } from './insights/InsightsTabHeader.jsx'
import { InsightsPreviewStats } from './insights/InsightsPreviewStats.jsx'
import { MonthlySnapshotGeneratorCard } from './insights/MonthlySnapshotGeneratorCard.jsx'
import {
  GoalInsightCard,
  buildGoalCardsFromSnapshot,
  buildPlaceholderGoalCards,
} from './insights/GoalInsightCard.jsx'
import { AskInsighteAiPanel } from './insights/AskInsighteAiPanel.jsx'
import { InsightsGenerationHistory } from './insights/InsightsGenerationHistory.jsx'

const RECENT_MONTHS = 6

async function fetchSnapshotById(caseId, snapshotId) {
  return apiFetch(`/api/v1/cases/${caseId}/insights/snapshots/${snapshotId}`)
}

function latestSnapshotForMonth(historyItems, month) {
  return historyItems
    .filter((item) => item.month === month)
    .sort((a, b) => (b.id ?? 0) - (a.id ?? 0))[0]
}

export function ClinicalInsightsPanel({ caseId, variant = 'therapist' }) {
  const navigate = useNavigate()
  const [month, setMonth] = useState(currentMonthValue())
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(true)
  const [previewError, setPreviewError] = useState('')
  const [snapshot, setSnapshot] = useState(null)
  const [recentHistory, setRecentHistory] = useState([])
  const [generating, setGenerating] = useState(false)
  const [asking, setAsking] = useState(false)
  const [message, setMessage] = useState('')

  const basePath = variant === 'admin'
    ? `/admin/cases/${caseId}`
    : `/therapist/cases/${caseId}`

  const loadRecentHistory = useCallback(async () => {
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/insights/snapshots`)
      const allowedMonths = new Set(monthOptions(RECENT_MONTHS).map((o) => o.value))
      const items = (data.items || []).filter((item) => allowedMonths.has(item.month))
      setRecentHistory(items)
      return items
    } catch {
      setRecentHistory([])
      return []
    }
  }, [caseId])

  const resolveSnapshotForMonth = useCallback(async (targetMonth, previewData, historyItems) => {
    if (previewData?.existing_snapshot_id) {
      try {
        const data = await fetchSnapshotById(caseId, previewData.existing_snapshot_id)
        setSnapshot(data)
        return
      } catch {
        /* fall through to history lookup */
      }
    }

    const match = latestSnapshotForMonth(historyItems, targetMonth)
    if (!match) {
      setSnapshot(null)
      return
    }

    if (match.ai_output_json || match.ai_output_text) {
      setSnapshot(match)
      return
    }

    try {
      const data = await fetchSnapshotById(caseId, match.id)
      setSnapshot(data)
    } catch {
      setSnapshot(null)
    }
  }, [caseId])

  useEffect(() => {
    loadRecentHistory()
  }, [loadRecentHistory])

  useEffect(() => {
    let cancelled = false

    async function loadPreviewForMonth() {
      setPreviewLoading(true)
      setPreviewError('')
      setSnapshot(null)
      setPreview(null)

      try {
        const data = await apiFetch(`/api/v1/cases/${caseId}/insights/data-preview?month=${month}`)
        if (cancelled) return
        setPreview(data)
      } catch {
        if (!cancelled) {
          setPreview(null)
          setPreviewError('Could not load data preview. Try again.')
        }
      } finally {
        if (!cancelled) setPreviewLoading(false)
      }
    }

    loadPreviewForMonth()
    return () => {
      cancelled = true
    }
  }, [caseId, month])

  useEffect(() => {
    if (!preview) return
    if (snapshot?.month === month) return

    let cancelled = false
    ;(async () => {
      await resolveSnapshotForMonth(month, preview, recentHistory)
      if (cancelled) return
    })()

    return () => {
      cancelled = true
    }
  }, [preview, month, recentHistory, snapshot?.month, resolveSnapshotForMonth])

  const goalCards = useMemo(() => {
    const generated = buildGoalCardsFromSnapshot(snapshot)
    if (generated.length) return generated
    return buildPlaceholderGoalCards(preview)
  }, [snapshot, preview])

  const handleGenerate = async (force = false) => {
    setGenerating(true)
    setMessage('')
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/insights/generate-snapshot`, {
        method: 'POST',
        body: JSON.stringify({ month, insight_type: 'full_snapshot', force_regenerate: force }),
      })
      setSnapshot(data)
      if (data.message) setMessage(data.message)
      loadRecentHistory()
    } catch (err) {
      setMessage(err.message || 'Could not generate snapshot. Try again.')
    } finally {
      setGenerating(false)
    }
  }

  const handleViewPrevious = async () => {
    await resolveSnapshotForMonth(month, preview, recentHistory)
    if (!preview?.existing_snapshot_id && !latestSnapshotForMonth(recentHistory, month)) {
      setMessage('No saved snapshot for this month yet.')
    }
  }

  const handleOpenHistory = (item) => {
    setMonth(item.month)
  }

  const handleSave = async () => {
    if (!snapshot?.id) return
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/insights/snapshots/${snapshot.id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ feedback_type: 'saved' }),
      })
      setSnapshot(data)
      loadRecentHistory()
    } catch (err) {
      setMessage(err.message || 'Could not save snapshot.')
    }
  }

  const handleSendReview = async () => {
    if (!snapshot?.id) return
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/insights/snapshots/${snapshot.id}/send-review`, {
        method: 'POST',
      })
      setSnapshot(data)
      loadRecentHistory()
    } catch (err) {
      setMessage(err.message || 'Could not send for review.')
    }
  }

  const handleAsk = async (question) => {
    if (!snapshot?.id) return null
    setAsking(true)
    try {
      return await apiFetch(`/api/v1/cases/${caseId}/insights/followup`, {
        method: 'POST',
        body: JSON.stringify({ snapshot_id: snapshot.id, question }),
      })
    } finally {
      setAsking(false)
    }
  }

  const handleCardAction = (action) => {
    if (action.action === 'add_goals') navigate(`${basePath}?tab=goals`)
    else if (action.action === 'add_report') navigate(`${basePath}?tab=reports&section=monthly`)
    else if (action.action === 'suggest_iep') navigate(`${basePath}?tab=reports&section=iep`)
    else if (action.action === 'view_evidence') navigate(`${basePath}?tab=logs`)
    else if (action.action === 'discuss_cm') navigate(`${basePath}?tab=reports`)
    else if (action.action === 'add_support' || action.action === 'add_iep') navigate(`${basePath}?tab=reports&section=iep`)
  }

  return (
    <div className="insights-tab">
      <InsightsTabHeader />

      {message ? <p className="insights-tab-message">{message}</p> : null}

      <div className="insights-tab-main">
        <InsightsPreviewStats
          preview={preview}
          loading={previewLoading}
          error={previewError}
        />

        <MonthlySnapshotGeneratorCard
          month={month}
          onMonthChange={setMonth}
          preview={preview}
          previewLoading={previewLoading}
          snapshot={snapshot}
          generating={generating}
          onGenerate={() => handleGenerate(false)}
          onViewPrevious={handleViewPrevious}
          onSave={handleSave}
          onAddToStrategies={() => navigate(`${basePath}?tab=strategies`)}
          onSendReview={handleSendReview}
          onRegenerate={() => handleGenerate(true)}
        />

        <section className="insights-goal-section" aria-label="Goal and strategy insights">
          <div className="insights-goal-grid insights-goal-grid--three">
            {goalCards.map((card) => (
              <GoalInsightCard key={card.title} card={card} onAction={handleCardAction} />
            ))}
          </div>
        </section>
      </div>

      <div className="insights-tab-ai-dock">
        <AskInsighteAiPanel snapshot={snapshot} onAsk={handleAsk} asking={asking} />
        <InsightsGenerationHistory
          items={recentHistory}
          onOpen={handleOpenHistory}
          emptyLabel="No snapshots in the last 6 months."
        />
      </div>
    </div>
  )
}

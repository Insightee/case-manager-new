import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFamilyPreview,
  canSubmitVoiceDraft,
  collectSessionStrategies,
  deriveSessionInsights,
  dismissEmergingGoal,
  emptyStructuredSession,
  getDraftReviewItems,
  getReviewSummary,
  inferResponseSignals,
  markGoalCandidateSent,
  recommendStrategies,
  setChallengeSummary,
  toggleResponseSignal,
  updateStrategyFeedback,
  addChallenge,
} from './structuredSessionEvidence.js'

function sessionWith(goals = [], extra = {}) {
  return { ...emptyStructuredSession({ sessionId: 1 }), goals, ...extra }
}

const pendingIepGoal = {
  goal_card_id: 5,
  goal_label: 'Turn-taking',
  match_type: 'active_iep',
  status: 'pending',
  strategies: [{ strategy_label: 'Visual timer', feedback: null }],
}

test('pending AI-matched goals block submit', () => {
  const gate = canSubmitVoiceDraft(sessionWith([pendingIepGoal]))
  assert.equal(gate.ok, false)
  assert.match(gate.reason, /resolve/i)
})

test('confirmed goal permits submit', () => {
  const gate = canSubmitVoiceDraft(sessionWith([{ ...pendingIepGoal, status: 'confirmed' }]))
  assert.equal(gate.ok, true)
})

test('no-goal reason permits submit without goals', () => {
  const gate = canSubmitVoiceDraft(sessionWith([], { no_goal_reason: 'regulation_day' }))
  assert.equal(gate.ok, true)
})

test('emerging goals never block submit', () => {
  const emerging = { goal_label: 'New pattern', match_type: 'new_observation', status: 'pending' }
  const gate = canSubmitVoiceDraft(sessionWith([emerging], { todays_story: 'A calm session.' }))
  assert.equal(gate.ok, true)
})

test('review items clear after confirming goals', () => {
  const before = getDraftReviewItems(sessionWith([pendingIepGoal]))
  assert.equal(before.length, 1)
  const after = getDraftReviewItems(sessionWith([{ ...pendingIepGoal, status: 'confirmed' }]))
  assert.equal(after.length, 0)
})

test('inferResponseSignals maps prose to vocabulary deterministically', () => {
  const signals = inferResponseSignals('She asked for a break and later calmed down and returned to the task')
  assert.ok(signals.includes('requested_break'))
  assert.ok(signals.includes('returned_after_regulation'))
})

test('toggleResponseSignal adds and removes', () => {
  const s1 = toggleResponseSignal(sessionWith(), 'engaged')
  assert.deepEqual(s1.child_response_signals, ['engaged'])
  const s2 = toggleResponseSignal(s1, 'engaged')
  assert.deepEqual(s2.child_response_signals, [])
})

test('strategy feedback updates goal-linked strategy in place', () => {
  const session = sessionWith([{ ...pendingIepGoal, status: 'confirmed' }])
  const row = collectSessionStrategies(session)[0]
  const updated = updateStrategyFeedback(session, row, 'worked_well')
  assert.equal(updated.goals[0].strategies[0].feedback, 'worked_well')
})

test('insights use cautious single-session wording', () => {
  const session = sessionWith([{ ...pendingIepGoal, status: 'confirmed' }])
  const withFeedback = updateStrategyFeedback(session, collectSessionStrategies(session)[0], 'did_not_work')
  const insights = deriveSessionInsights(withFeedback)
  assert.ok(insights.some((line) => /did not seem to help today/.test(line)))
  assert.ok(insights.some((line) => /evidence is still limited/i.test(line)))
})

test('recommendStrategies is deterministic, max 2, skips used and dismissed', () => {
  const session = sessionWith([{ ...pendingIepGoal, status: 'confirmed' }], {
    dismissed_recommendations: ['choice board'],
  })
  const repo = {
    strategies: [
      { label: 'Visual timer', goal_card_id: 5 }, // used today → skipped
      { label: 'Choice board', goal_card_id: 5 }, // dismissed → skipped
      { label: 'First-then card', goal_card_id: 5 },
      { label: 'Quiet corner', goal_card_id: 5 },
      { label: 'Extra option', goal_card_id: 5 },
    ],
  }
  const recs = recommendStrategies(session, repo)
  assert.deepEqual(recs.map((r) => r.label), ['First-then card', 'Quiet corner'])
})

test('markGoalCandidateSent records candidate without touching evidence', () => {
  const emerging = { goal_label: 'New pattern', match_type: 'new_observation', status: 'pending' }
  const session = sessionWith([emerging])
  const updated = markGoalCandidateSent(session, session.goals[0], { id: 9 })
  assert.equal(updated.goal_candidates.length, 1)
  assert.equal(updated.goal_candidates[0].candidate_id, 9)
  assert.equal(updated.goals[0].candidate_status, 'pending_review')
})

test('dismissEmergingGoal removes the candidate from the draft', () => {
  const emerging = { goal_label: 'New pattern', match_type: 'new_observation', status: 'pending' }
  const session = sessionWith([emerging])
  const updated = dismissEmergingGoal(session, session.goals[0])
  assert.equal(updated.goals.length, 0)
})

test('addChallenge appends an editable therapist entry', () => {
  const updated = addChallenge(sessionWith(), 'Loud hallway')
  assert.equal(updated.challenge_observations.length, 1)
  assert.equal(updated.challenge_observations[0].source, 'therapist')
  assert.equal(updated.challenge_observations[0].flag_cm_review, false)
})

test('buildFamilyPreview uses confirmed goals only', () => {
  const session = sessionWith([], { child_response_signals: ['requested_break'] })
  session.goals = [
    {
      ...pendingIepGoal,
      status: 'confirmed',
      strategies: [{ strategy_label: 'Visual timer', feedback: 'worked_well' }],
    },
    { goal_label: 'Emerging', match_type: 'new_observation', status: 'pending' },
  ]
  const preview = buildFamilyPreview(session)
  assert.deepEqual(preview.worked_on, ['Turn-taking'])
  assert.ok(preview.appeared_helpful.includes('Visual timer'))
  assert.ok(preview.strength_highlight.some((s) => s.toLowerCase().includes('break')))
})

test('getReviewSummary counts pending goals', () => {
  const summary = getReviewSummary(sessionWith([pendingIepGoal]))
  assert.equal(summary.pendingGoals, 1)
  assert.equal(summary.hasUnresolved, true)
})

test('setChallengeSummary keeps a single summary entry', () => {
  const updated = setChallengeSummary(sessionWith(), 'Noise made participation harder.')
  assert.equal(updated.challenge_observations.length, 1)
  assert.match(updated.challenge_observations[0].text, /Noise/)
})

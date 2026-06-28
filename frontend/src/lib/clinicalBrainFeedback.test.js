import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { feedbackBadgeLabel, feedbackMapByStrategy } from './clinicalBrainFeedbackApi.js'

describe('clinicalBrainFeedback', () => {
  it('maps feedback status to badge labels', () => {
    assert.equal(feedbackBadgeLabel('accepted'), 'Helpful for this child')
    assert.equal(feedbackBadgeLabel('needs_cm_input'), 'Needs CM support')
  })

  it('indexes feedback rows by strategy id', () => {
    const map = feedbackMapByStrategy([
      { strategy_repository_item_id: 5, feedback_status: 'accepted' },
      { strategy_repository_item_id: 9, feedback_status: 'adapted' },
    ])
    assert.equal(map.get(5).feedback_status, 'accepted')
    assert.equal(map.get(9).feedback_status, 'adapted')
  })
})

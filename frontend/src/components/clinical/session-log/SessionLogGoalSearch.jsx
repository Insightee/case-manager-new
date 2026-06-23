import { useMemo, useState } from 'react'
import { searchGoalStrategyPool } from '../../../lib/sessionLogGoals.js'

export function SessionLogGoalSearch({ repo, readOnly, onPickGoal, onPickStrategy }) {
  const [query, setQuery] = useState('')
  const results = useMemo(() => searchGoalStrategyPool(query, repo), [query, repo])

  const hasResults =
    query.trim().length > 0 &&
    (results.goals.length > 0 || results.strategies.length > 0 || results.suggestions.length > 0)

  if (readOnly) return null

  return (
    <div className="sl-goal-search">
      <label className="sl-goal-search__field">
        <span className="visually-hidden">Search goals and strategies</span>
        <input
          type="search"
          value={query}
          placeholder="Search goals, strategies, or type a concern…"
          onChange={(e) => setQuery(e.target.value)}
          className="sl-goal-search__input"
        />
      </label>

      {hasResults ? (
        <div className="sl-goal-search__results">
          {results.suggestions.length ? (
            <div className="sl-goal-search__group">
              <p className="sl-goal-search__label">Suggested matches</p>
              {results.suggestions.map((s) => (
                <button
                  key={`${s.type}-${s.label}`}
                  type="button"
                  className="sl-goal-search__row sl-goal-search__row--suggestion"
                  onClick={() =>
                    s.type === 'goal' ? onPickGoal?.({ label: s.label, source: 'suggestion' }) : onPickStrategy?.({ label: s.label })
                  }
                >
                  <span>{s.label}</span>
                  <span className="sl-goal-search__badge">{s.type === 'goal' ? 'Goal' : 'Strategy'}</span>
                </button>
              ))}
            </div>
          ) : null}
          {results.goals.map((g) => (
            <button
              key={`g-${g.goal_card_id || g.id || g.label}`}
              type="button"
              className="sl-goal-search__row"
              onClick={() => onPickGoal?.(g)}
            >
              <span>{g.label}</span>
              <span className="sl-goal-search__badge">{g.source === 'iep' ? 'IEP' : 'Case goal'}</span>
            </button>
          ))}
          {results.strategies.map((s) => (
            <button
              key={`s-${s.strategy_id || s.id || s.label}`}
              type="button"
              className="sl-goal-search__row"
              onClick={() => onPickStrategy?.(s)}
            >
              <span>{s.label}</span>
              <span className="sl-goal-search__badge">{s.category || 'Strategy'}</span>
            </button>
          ))}
        </div>
      ) : query.trim() ? (
        <p className="gs-muted sl-goal-search__empty">No matches — try a concern like “classroom transition” or add a custom goal.</p>
      ) : null}
    </div>
  )
}

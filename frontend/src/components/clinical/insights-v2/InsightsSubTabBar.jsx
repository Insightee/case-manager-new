import { useSearchParams } from 'react-router-dom'

export const INSIGHTS_SUB_TABS = [
  { id: 'weekly', label: 'Weekly Insights' },
  { id: 'ask', label: 'Ask' },
]

export function useInsightsSubTab() {
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get('insightsView') === 'ask' ? 'ask' : 'weekly'

  const setView = (next) => {
    const params = new URLSearchParams(searchParams)
    params.set('tab', 'insights')
    if (next === 'ask') {
      params.set('insightsView', 'ask')
    } else {
      params.delete('insightsView')
    }
    setSearchParams(params, { replace: true })
  }

  return { view, setView }
}

export function InsightsSubTabBar({ activeView, onChange }) {
  return (
    <div className="ci-subtabs" role="tablist" aria-label="Insights views">
      {INSIGHTS_SUB_TABS.map((tab) => {
        const selected = activeView === tab.id
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`ci-subtab-${tab.id}`}
            aria-selected={selected}
            aria-controls={`ci-subtabpanel-${tab.id}`}
            className={`ci-subtabs__pill${selected ? ' ci-subtabs__pill--active' : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

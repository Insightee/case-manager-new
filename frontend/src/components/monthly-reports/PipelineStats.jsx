import { ReportsMetricCard, ReportsMetricGrid } from '../reports-hub/ReportsMetricGrid.jsx'

const CARDS = [
  { key: 'draft', label: 'Draft', tone: 'draft' },
  { key: 'underReview', label: 'Under Review', tone: 'underReview' },
  { key: 'published', label: 'Published', tone: 'published' },
  { key: 'overdue', label: 'Overdue', tone: 'overdue' },
]

export function PipelineStats({ counts, activeFilter, onFilter }) {
  return (
    <ReportsMetricGrid aria-label="Report pipeline overview">
      {CARDS.map((c) => (
        <ReportsMetricCard
          key={c.key}
          label={c.label}
          value={counts[c.key] ?? 0}
          tone={c.tone}
          active={activeFilter === c.key}
          onClick={() => onFilter(c.key)}
        />
      ))}
    </ReportsMetricGrid>
  )
}

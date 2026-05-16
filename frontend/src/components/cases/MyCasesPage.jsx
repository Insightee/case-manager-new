import { useMemo, useState } from 'react'
import myCasesData from '../../data/myCases.json'
import { CasesPageHeader } from './CasesPageHeader.jsx'
import { FilterBar } from './FilterBar.jsx'
import { StatCard } from './StatCard.jsx'
import { CaseCard } from './CaseCard.jsx'
import './my-cases.css'

function flattenTableRows(sections) {
  const rows = []
  for (const sec of sections) {
    for (const c of sec.cases) {
      if (c.layout === 'standard') {
        rows.push({
          caseId: c.caseId,
          child: c.child,
          service: c.service,
          stage: c.stage,
          next: c.due || '—',
        })
      } else if (c.layout === 'split') {
        rows.push({
          caseId: c.caseId,
          child: c.child,
          service: c.left.service,
          stage: `${c.left.tag} / ${c.right.title}`,
          next: c.right.note,
        })
      } else if (c.layout === 'dual') {
        rows.push({
          caseId: c.left.caseId,
          child: c.left.child,
          service: c.left.service,
          stage: c.left.stage,
          next: c.left.due || '—',
        })
        rows.push({
          caseId: c.right.caseId,
          child: c.right.child,
          service: c.right.service,
          stage: c.right.stage,
          next: c.right.due || '—',
        })
      } else if (c.layout === 'completed') {
        rows.push({
          caseId: c.caseId,
          child: c.child,
          service: c.service,
          stage: c.panels[0]?.label || 'Completed',
          next: c.panels[1]?.label || '—',
        })
      }
    }
  }
  return rows
}

function SectionHeader({ title, tone, count }) {
  return (
    <div className="ic-section-head">
      <h2 className="ic-section-head__title">{title}</h2>
      <span className={`ic-section-count ic-section-count--${tone}`}>{count}</span>
    </div>
  )
}

export function MyCasesPage() {
  const [view, setView] = useState('grid')
  const tableRows = useMemo(() => flattenTableRows(myCasesData.sections), [])

  return (
    <div className="ic-my-cases">
      <CasesPageHeader />
      <FilterBar view={view} onViewChange={setView} />

      <section className="ic-stats" aria-label="Case summary">
        {myCasesData.stats.map((s) => (
          <StatCard key={s.id} label={s.label} value={s.value} variant={s.variant} />
        ))}
      </section>

      {view === 'grid' ? (
        <div className="ic-board">
          {myCasesData.sections.map((sec) => (
            <section key={sec.id} className="ic-board__column">
              <SectionHeader title={sec.title} tone={sec.tone} count={sec.count} />
              <div className="ic-board__cards">
                {sec.cases.map((c, idx) => (
                  <CaseCard key={`${sec.id}-${idx}`} data={c} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="ic-table-card">
          <div className="ic-table-head">
            <h3>All cases</h3>
            <button type="button" className="ic-btn-export">
              Export
            </button>
          </div>
          <div className="ic-table-wrap">
            <table className="ic-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Child</th>
                  <th>Service</th>
                  <th>Stage</th>
                  <th>Next due</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((r) => (
                  <tr key={`${r.caseId}-${r.child}`}>
                    <td>{r.caseId}</td>
                    <td>{r.child}</td>
                    <td>{r.service}</td>
                    <td>{r.stage}</td>
                    <td>{r.next}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

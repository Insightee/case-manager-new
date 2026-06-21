import { ClinicalVisibilityBadge } from './ClinicalVisibilityBadge.jsx'

export function ClinicalSectionRail({ title = 'Report Sections', note, aiNote, sections = [], footer }) {
  return (
    <aside className="clinical-section-rail" aria-label={title}>
      <h3 className="clinical-section-rail__title">{title}</h3>
      {note ? <p className="clinical-section-rail__note">{note}</p> : null}
      {aiNote ? <p className="clinical-section-rail__note">{aiNote}</p> : null}
      {sections.length ? (
        <ul className="clinical-section-rail__list">
          {sections.map((s) => (
            <li key={s.key || s.label} className="clinical-section-rail__item">
              <span>{s.label}</span>
              {s.visibility ? <ClinicalVisibilityBadge visibility={s.visibility} /> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {footer}
    </aside>
  )
}

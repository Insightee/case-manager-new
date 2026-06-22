import { useEffect, useId, useRef, useState } from 'react'

export function ScoreHelpButton({ title, body, compact = false }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const popId = useId()

  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <span className={`sl-score-help${compact ? ' sl-score-help--compact' : ''}`} ref={wrapRef}>
      <button
        type="button"
        className="sl-score-help__btn"
        aria-expanded={open}
        aria-controls={popId}
        aria-label={`What is ${title}?`}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open ? (
        <div id={popId} className="sl-score-help__pop" role="tooltip">
          <p className="sl-score-help__pop-title">{title}</p>
          <div className="sl-score-help__pop-body">{body}</div>
        </div>
      ) : null}
    </span>
  )
}

export function MeasurementHelpTicker() {
  return (
    <ScoreHelpButton
      compact
      title="Today's measurement scales"
      body={
        <ul className="sl-score-help__list">
          <li>
            <strong>Participation</strong> — 0 not available · 1 observed only · 2 partial · 3 active with support · 4
            independent / self-led
          </li>
          <li>
            <strong>Independence level</strong> — 4 no support · 3 light prompt · 2 moderate · 1 high · 0 full support
          </li>
          <li>
            <strong>Goal achievement</strong> — 0 not observed · 1 emerging · 2 attempted · 3 mostly achieved · 4
            achieved today
          </li>
        </ul>
      }
    />
  )
}

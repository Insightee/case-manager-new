import { useEffect, useState } from 'react'
import { hydrateReportImages, sanitizeReportHtml } from '../../lib/reportHtml.js'
import './report-editor.css'

export function ReportHtmlView({ html, className = 'report-html-view' }) {
  const [displayHtml, setDisplayHtml] = useState('')

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!html) {
        setDisplayHtml('')
        return
      }
      try {
        const hydrated = await hydrateReportImages(html)
        if (!cancelled) setDisplayHtml(hydrated)
      } catch {
        if (!cancelled) setDisplayHtml(sanitizeReportHtml(html))
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [html])

  if (!html) return <p className="text-sm text-slate-500">No report body yet.</p>

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: displayHtml || sanitizeReportHtml(html) }}
    />
  )
}

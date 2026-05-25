import { useEffect, useRef, useState } from 'react'
import { hydrateReportImages, revokeBlobUrlsInHtml, sanitizeReportHtml } from '../../lib/reportHtml.js'
import './report-editor.css'

export function ReportHtmlView({ html, className = 'report-html-view' }) {
  const [displayHtml, setDisplayHtml] = useState('')
  const displayRef = useRef('')

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!html) {
        displayRef.current = ''
        setDisplayHtml('')
        return
      }
      try {
        const hydrated = await hydrateReportImages(html)
        if (cancelled) {
          revokeBlobUrlsInHtml(hydrated)
          return
        }
        displayRef.current = hydrated
        setDisplayHtml(hydrated)
      } catch {
        if (!cancelled) {
          const fallback = sanitizeReportHtml(html)
          displayRef.current = fallback
          setDisplayHtml(fallback)
        }
      }
    }
    run()
    return () => {
      cancelled = true
      revokeBlobUrlsInHtml(displayRef.current)
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

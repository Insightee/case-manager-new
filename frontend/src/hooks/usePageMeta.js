import { useEffect } from 'react'

export const APP_NAME = 'InsightCase'
export const DEFAULT_DESCRIPTION =
  'Case-centric care management for therapists, families, HR, and operations — session logs, reports, billing, and IEP in one platform.'

/**
 * Sets document title and meta description for SEO and accessibility.
 */
export function usePageMeta({ title, description = DEFAULT_DESCRIPTION } = {}) {
  useEffect(() => {
    document.title = title ? `${title} — ${APP_NAME}` : APP_NAME

    let meta = document.querySelector('meta[name="description"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'description')
      document.head.appendChild(meta)
    }
    meta.setAttribute('content', description)
  }, [title, description])
}

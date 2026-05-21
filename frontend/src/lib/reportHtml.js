import DOMPurify from 'dompurify'
import { apiFetchBlob } from './apiClient.js'

const API_PREFIX = '/api/v1/reports/images/'

export function sanitizeReportHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ['img'],
    ADD_ATTR: ['src', 'alt', 'class'],
  })
}

/** Replace authenticated image paths with blob URLs for display. */
export async function hydrateReportImages(html) {
  if (!html) return ''
  const safe = sanitizeReportHtml(html)
  const doc = new DOMParser().parseFromString(safe, 'text/html')
  const imgs = [...doc.querySelectorAll('img')]
  await Promise.all(
    imgs.map(async (img) => {
      const src = img.getAttribute('src') || ''
      const match = src.match(/\/api\/v1\/reports\/images\/(\d+)/)
      if (!match) return
      try {
        const blob = await apiFetchBlob(`/api/v1/reports/images/${match[1]}`)
        img.setAttribute('src', URL.createObjectURL(blob))
      } catch {
        img.setAttribute('alt', 'Image unavailable')
      }
    }),
  )
  return doc.body.innerHTML
}

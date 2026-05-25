import DOMPurify from 'dompurify'
import { apiFetchBlob } from './apiClient.js'

const REPORT_IMAGE_RE = /\/api\/v1\/reports\/images\/\d+/

export function sanitizeReportHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ['img'],
    ADD_ATTR: ['src', 'alt', 'class', 'data-api-src'],
  })
}

/** Persist API image paths in saved HTML (strip blob display URLs). */
export function dehydrateReportImages(html) {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.querySelectorAll('img').forEach((img) => {
    const src = img.getAttribute('src') || ''
    let api = img.getAttribute('data-api-src')
    if (!api && REPORT_IMAGE_RE.test(src)) {
      api = src
    }
    if (api && REPORT_IMAGE_RE.test(api)) {
      img.setAttribute('src', api)
      img.removeAttribute('data-api-src')
    } else if (src.startsWith('blob:')) {
      img.removeAttribute('src')
      img.setAttribute('alt', img.getAttribute('alt') || 'Image unavailable')
    }
  })
  return doc.body.innerHTML
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
      const apiSrc = img.getAttribute('data-api-src') || src
      const match = apiSrc.match(/\/api\/v1\/reports\/images\/(\d+)/)
      if (!match) return
      try {
        const blob = await apiFetchBlob(`/api/v1/reports/images/${match[1]}`)
        img.setAttribute('data-api-src', apiSrc)
        img.setAttribute('src', URL.createObjectURL(blob))
      } catch {
        img.setAttribute('alt', 'Image unavailable')
      }
    }),
  )
  return doc.body.innerHTML
}

export function revokeBlobUrlsInHtml(html) {
  if (!html) return
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.querySelectorAll('img[src^="blob:"]').forEach((img) => {
    const src = img.getAttribute('src')
    if (src?.startsWith('blob:')) URL.revokeObjectURL(src)
  })
}

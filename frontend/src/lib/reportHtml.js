import DOMPurify from 'dompurify'
import { apiFetchBlob } from './apiClient.js'

const REPORT_IMAGE_RE = /\/api\/v1\/reports\/images\/\d+/
const blobUrlCache = new Map()

function imageIdFromSrc(src) {
  const match = (src || '').match(/\/api\/v1\/reports\/images\/(\d+)/)
  return match ? match[1] : null
}

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

/** Replace authenticated image paths with blob URLs for display (cached per image id). */
export async function hydrateReportImages(html) {
  if (!html) return ''
  const safe = sanitizeReportHtml(html)
  const doc = new DOMParser().parseFromString(safe, 'text/html')
  const imgs = [...doc.querySelectorAll('img')]
  await Promise.all(
    imgs.map(async (img) => {
      const src = img.getAttribute('src') || ''
      const apiSrc = img.getAttribute('data-api-src') || src
      const imageId = imageIdFromSrc(apiSrc)
      if (!imageId) return
      img.setAttribute('data-api-src', apiSrc)
      if (blobUrlCache.has(imageId)) {
        img.setAttribute('src', blobUrlCache.get(imageId))
        return
      }
      try {
        const blob = await apiFetchBlob(`/api/v1/reports/images/${imageId}`)
        const blobUrl = URL.createObjectURL(blob)
        blobUrlCache.set(imageId, blobUrl)
        img.setAttribute('src', blobUrl)
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

export function registerReportImageBlobUrl(imageId, blobUrl) {
  if (imageId == null || !blobUrl) return
  const key = String(imageId)
  const existing = blobUrlCache.get(key)
  if (existing && existing !== blobUrl) URL.revokeObjectURL(existing)
  blobUrlCache.set(key, blobUrl)
}

const DOC_PATTERN = /^https:\/\/docs\.google\.com\/document\//
const FILE_PATTERN = /^https:\/\/drive\.google\.com\/file\//
const OPEN_PATTERN = /^https:\/\/drive\.google\.com\/open\?id=/
const FOLDER_PATTERN = /drive\.google\.com\/drive\/folders/

export function validateGoogleLink(url) {
  const trimmed = (url || '').trim()
  if (!trimmed) {
    return { ok: false, message: 'Enter a Google Docs or Drive file link.' }
  }
  let parsed
  try {
    parsed = new URL(trimmed)
  } catch {
    return { ok: false, message: 'Enter a valid https URL.' }
  }
  if (parsed.protocol !== 'https:') {
    return { ok: false, message: 'Only https links are allowed.' }
  }
  if (FOLDER_PATTERN.test(parsed.href)) {
    return { ok: false, message: 'Folder links are not supported in P1. Link to a single file or Doc instead.' }
  }
  const href = parsed.href
  if (DOC_PATTERN.test(href) || FILE_PATTERN.test(href) || OPEN_PATTERN.test(href)) {
    return { ok: true, normalized: href }
  }
  return {
    ok: false,
    message: 'Use a Google Docs document link or a Drive file link (not a folder).',
  }
}

export const GOOGLE_LINK_WARNING =
  'Access depends on Google sharing settings. InsightCase stores the link only and does not sync Google content.'

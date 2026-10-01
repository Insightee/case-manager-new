export const BIO_MIN_WORDS = 40
export const BIO_MAX_CHARS = 800

export const QUALITY_WEIGHTS = {
  avatar: 20,
  home_address: 10,
  pincode: 10,
  phone: 10,
  email: 5,
  short_bio: 20,
  degree: 15,
  services_offered: 10,
}

export const QUALITY_REMINDERS = {
  avatar: 'Your profile photo still needs to be added so families recognise you.',
  home_address: 'Add your street and city so we have a complete address.',
  pincode: 'Add your 6-digit pincode so we have a complete address.',
  phone: 'Use a 10-digit mobile number.',
  email: 'Add your email id so your team can reach you.',
  short_bio: 'Your bio needs more than 40 words. This is what your clients see about you.',
  degree: 'Add at least one degree (title and year).',
  services_offered: 'Select at least one service you offer.',
}

export function wordCount(text) {
  if (!text) return 0
  return text.trim().slice(0, BIO_MAX_CHARS).split(/\s+/).filter(Boolean).length
}

export function normalizePhoneDigits(phone) {
  if (!phone) return ''
  let digits = String(phone).replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) digits = digits.slice(2)
  if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1)
  return digits
}

export function isTenDigitPhone(phone) {
  return normalizePhoneDigits(phone).length === 10
}

export function isSixDigitPincode(pincode) {
  return /^\d{6}$/.test(String(pincode || '').trim())
}

export function normalizeQualificationEntries(raw) {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : String(raw).split('\n')
  const entries = []
  for (const item of list) {
    if (typeof item === 'string') {
      const title = item.trim()
      if (title) entries.push({ kind: 'certificate', title, year: null })
      continue
    }
    if (!item || typeof item !== 'object') continue
    const kind = item.kind === 'degree' ? 'degree' : 'certificate'
    const title = String(item.title || '').trim()
    if (!title) continue
    const yearNum = item.year === '' || item.year == null ? null : Number(item.year)
    const year = Number.isInteger(yearNum) && yearNum >= 1950 && yearNum <= 2035 ? yearNum : null
    entries.push({ kind, title: title.slice(0, 255), year })
  }
  return entries
}

export function hasCompleteDegree(entries) {
  return normalizeQualificationEntries(entries).some((e) => e.kind === 'degree' && e.title && e.year)
}

export function addQualificationEntry(entries, draft) {
  const title = String(draft?.title || '').trim()
  const yearNum = Number(draft?.year)
  if (!title || !Number.isInteger(yearNum)) return normalizeQualificationEntries(entries)
  const kind = draft?.kind === 'degree' ? 'degree' : 'certificate'
  return [...normalizeQualificationEntries(entries), { kind, title: title.slice(0, 255), year: yearNum }]
}

export function removeQualificationEntry(entries, index) {
  return normalizeQualificationEntries(entries).filter((_, i) => i !== index)
}

export function evaluateProfileQuality({
  email,
  phone,
  avatarPath,
  avatarUrl,
  addressLine1,
  city,
  pincode,
  displayName,
  fullName,
  shortBio,
  servicesOffered,
  qualificationEntries,
} = {}) {
  const entries = normalizeQualificationEntries(qualificationEntries)
  const checks = {
    avatar: Boolean(String(avatarPath || avatarUrl || '').trim()),
    home_address: Boolean(String(addressLine1 || '').trim() && String(city || '').trim()),
    pincode: isSixDigitPincode(pincode),
    phone: isTenDigitPhone(phone),
    email: Boolean(String(email || '').trim()),
    short_bio: wordCount(shortBio) > BIO_MIN_WORDS,
    degree: hasCompleteDegree(entries),
    services_offered: (servicesOffered || []).length > 0,
  }
  const items = []
  const reminders = []
  let score = 0
  for (const [key, weight] of Object.entries(QUALITY_WEIGHTS)) {
    const passed = Boolean(checks[key])
    items.push({ key, passed, points: passed ? weight : 0, max: weight })
    if (passed) score += weight
    else reminders.push({ key, message: QUALITY_REMINDERS[key] })
  }
  const name = String(displayName || fullName || '').trim()
  const autoPass = score > 80 && checks.avatar && checks.pincode && checks.short_bio && checks.degree
  return {
    score,
    percent: score,
    items,
    reminders,
    can_submit: score >= 50 && Boolean(name),
    auto_pass: autoPass,
    word_count: wordCount(shortBio),
  }
}

export function submitHelperText(quality) {
  if (!quality) return ''
  if (quality.auto_pass) return 'This will publish now.'
  if (quality.can_submit) return 'You can send this for admin review, or add a few more details to publish now.'
  return 'Looks like we still need a few details before we can send this for review.'
}

export function isProfileNudgeNeeded(completion) {
  if (!completion) return false
  if (typeof completion.needs_nudge === 'boolean') return completion.needs_nudge
  return completion.complete === false
}

/** Parse therapist primary-CM bulk update CSV / spreadsheet paste uploads. */

function parseDelimitedLine(line, delimiter) {
  if (delimiter === '\t') {
    return line.split('\t').map((cell) => cell.trim().replace(/^"|"$/g, ''))
  }
  const row = []
  const pattern = /("([^"]*(?:""[^"]*)*)"|([^",\r\n]*))/gi
  pattern.lastIndex = 0
  let match
  while ((match = pattern.exec(line)) !== null) {
    if (match.index === pattern.lastIndex) pattern.lastIndex++
    const rawValue = match[2] !== undefined ? match[2] : match[3]
    row.push(rawValue ? rawValue.replace(/""/g, '"').trim() : '')
  }
  if (line.endsWith(',') === false && row[row.length - 1] === '') row.pop()
  return row
}

function detectDelimiter(text) {
  const firstLine = String(text || '')
    .split(/\r?\n/)
    .find((line) => line.trim())
  if (!firstLine) return ','
  const tabs = (firstLine.match(/\t/g) || []).length
  const commas = (firstLine.match(/,/g) || []).length
  return tabs > commas ? '\t' : ','
}

function parseDelimited(text) {
  const delimiter = detectDelimiter(text)
  const lines = []
  for (const line of String(text || '').split(/\r?\n/)) {
    if (!line.trim()) continue
    lines.push(parseDelimitedLine(line, delimiter))
  }
  return lines
}

function headerIndex(headers, aliases) {
  for (const alias of aliases) {
    const idx = headers.indexOf(alias)
    if (idx >= 0) return idx
  }
  return -1
}

const HEADER_ALIASES = {
  therapist_id: ['therapist id', 'therapist_id', 'external_employee_id'],
  email: ['email', 'therapist email'],
  primary_cm_name: ['primary cm', 'primary_cm', 'primary case manager'],
  case_manager_email: ['case manager email', 'case_manager_email', 'cm email'],
}

export function parseTherapistCmBulkCsv(text) {
  const rawRows = parseDelimited(text)
  if (!rawRows.length) return []

  const headers = rawRows[0].map((cell) => cell.toLowerCase().trim())
  const hasKnownHeader = Object.values(HEADER_ALIASES).some((aliases) =>
    aliases.some((alias) => headers.includes(alias)),
  )
  const dataRows = hasKnownHeader ? rawRows.slice(1) : rawRows

  const indexes = Object.fromEntries(
    Object.entries(HEADER_ALIASES).map(([key, aliases]) => [key, headerIndex(headers, aliases)]),
  )

  const readCell = (row, key) => {
    const idx = indexes[key]
    if (idx < 0) return ''
    return (row[idx] ?? '').trim()
  }

  return dataRows
    .map((row) => ({
      therapist_id: readCell(row, 'therapist_id') || null,
      email: readCell(row, 'email') || null,
      primary_cm_name: readCell(row, 'primary_cm_name') || null,
      case_manager_email: readCell(row, 'case_manager_email'),
    }))
    .filter((row) => row.email || row.therapist_id || row.case_manager_email)
}

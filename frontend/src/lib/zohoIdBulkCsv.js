/** Parse case Zoho ID bulk CSV / spreadsheet paste (Case code + Zoho ID). */

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

const CASE_CODE_RE = /^IC-\d{4}-[A-Z0-9]+-\d+/i
const ZOHO_ID_RE = /^(INS|CUS|B2B)-/i
const EMPTY_MARKERS = new Set(['', '-', '—', '–', 'n/a', 'na', 'none'])

const HEADER_ALIASES = {
  case_code: ['cases', 'case', 'case id', 'case_code', 'case code', 'caseid'],
  zoho_id: ['zoho id', 'zoho_id', 'zoho', 'zohoid', 'zoho customer id'],
}

function isEmptyCell(value) {
  return EMPTY_MARKERS.has(String(value || '').trim().toLowerCase())
}

function inferFromCells(cells) {
  let case_code = ''
  let zoho_id = ''
  for (const cell of cells) {
    const value = (cell || '').trim()
    if (!value || isEmptyCell(value)) continue
    if (!case_code && CASE_CODE_RE.test(value)) case_code = value
    else if (!zoho_id && ZOHO_ID_RE.test(value)) zoho_id = value
  }
  return { case_code: case_code || null, zoho_id: zoho_id || null }
}

export function parseCaseZohoIdBulkCsv(text) {
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
    .map((row) => {
      if (hasKnownHeader) {
        const case_code = readCell(row, 'case_code')
        const zoho_id = readCell(row, 'zoho_id')
        if (case_code || zoho_id) {
          return {
            case_code: isEmptyCell(case_code) ? null : case_code || null,
            zoho_id: isEmptyCell(zoho_id) ? null : zoho_id || null,
          }
        }
      }
      return inferFromCells(row)
    })
    .filter((row) => row.case_code || row.zoho_id)
}

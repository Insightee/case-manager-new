import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export function createProductionReport() {
  const runId = `${Date.now()}`
  const report = {
    runId,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    baseURL: process.env.PLAYWRIGHT_BASE_URL || '',
    apiURL: process.env.PLAYWRIGHT_API_URL || '',
    steps: [],
    artifacts: {},
  }

  return {
    runId,
    log(step, status, detail = '') {
      report.steps.push({
        step,
        status,
        detail,
        at: new Date().toISOString(),
      })
    },
    setArtifact(key, value) {
      report.artifacts[key] = value
    },
    getArtifacts() {
      return { ...report.artifacts }
    },
    finish() {
      report.finishedAt = new Date().toISOString()
      const outDir = path.resolve(__dirname, '../../../docs/reports')
      fs.mkdirSync(outDir, { recursive: true })
      const jsonPath = path.join(outDir, 'production-e2e-latest.json')
      fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2))
      const mdPath = path.join(outDir, 'production-e2e-latest.md')
      fs.writeFileSync(mdPath, toMarkdown(report))
      return { jsonPath, mdPath }
    },
  }
}

function toMarkdown(report) {
  const lines = [
    '# Production E2E report',
    '',
    `| Field | Value |`,
    `|-------|--------|`,
    `| Run ID | \`${report.runId}\` |`,
    `| Started | ${report.startedAt} |`,
    `| Finished | ${report.finishedAt || '—'} |`,
    `| UI | ${report.baseURL} |`,
    `| API | ${report.apiURL} |`,
    '',
  ]
  if (Object.keys(report.artifacts).length) {
    lines.push('## Created data', '')
    for (const [k, v] of Object.entries(report.artifacts)) {
      lines.push(`- **${k}:** ${v}`)
    }
    lines.push('')
  }
  lines.push('## Steps', '')
  lines.push('| Step | Status | Detail | Time |')
  lines.push('|------|--------|--------|------|')
  for (const s of report.steps) {
    const detail = String(s.detail || '').replace(/\|/g, '\\|').replace(/\n/g, ' ')
    lines.push(`| ${s.step} | ${s.status} | ${detail} | ${s.at} |`)
  }
  const passed = report.steps.filter((s) => s.status === 'PASS').length
  const failed = report.steps.filter((s) => s.status === 'FAIL').length
  lines.push('', `**Summary:** ${passed} passed, ${failed} failed, ${report.steps.length} total.`)
  return lines.join('\n')
}

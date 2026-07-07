/**
 * Build docs/THERAPIST_PORTAL_GUIDE.pdf from Markdown + CSS.
 * Run from repo root: node scripts/generate-therapist-guide-pdf.mjs
 */
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const MD_PATH = path.join(ROOT, 'docs', 'THERAPIST_PORTAL_GUIDE.md')
const CSS_PATH = path.join(ROOT, 'docs', 'therapist-portal-guide.css')
const PDF_PATH = path.join(ROOT, 'docs', 'THERAPIST_PORTAL_GUIDE.pdf')
const HTML_PATH = path.join(ROOT, 'docs', '.therapist-portal-guide.html')

const require = createRequire(path.join(ROOT, 'frontend', 'package.json'))
const { chromium } = require('playwright')

const md = fs.readFileSync(MD_PATH, 'utf8')
const css = fs.readFileSync(CSS_PATH, 'utf8')
const bodyHtml = execSync('npx --yes marked --gfm', {
  cwd: ROOT,
  input: md,
  encoding: 'utf8',
  stdio: ['pipe', 'pipe', 'inherit'],
})

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>InsighteCase Therapist Portal Guide</title>
  <style>${css}</style>
</head>
<body>${bodyHtml}</body>
</html>`

fs.writeFileSync(HTML_PATH, html, 'utf8')

const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  await page.goto(`file:///${HTML_PATH.replace(/\\/g, '/')}`, { waitUntil: 'networkidle' })
  await page.pdf({
    path: PDF_PATH,
    format: 'A4',
    printBackground: true,
    margin: { top: '18mm', right: '16mm', bottom: '18mm', left: '16mm' },
  })
} finally {
  await browser.close()
  fs.unlinkSync(HTML_PATH)
}

console.log(`Wrote ${PDF_PATH}`)

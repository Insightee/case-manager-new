#!/usr/bin/env node
import { writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { buildVersionManifest } from './releaseLabel.mjs'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function resolveBuildId() {
  if (process.env.VITE_BUILD_ID) return String(process.env.VITE_BUILD_ID).slice(0, 64)
  if (process.env.VERCEL_GIT_COMMIT_SHA) return String(process.env.VERCEL_GIT_COMMIT_SHA).slice(0, 12)
  if (process.env.RAILWAY_GIT_COMMIT_SHA) return String(process.env.RAILWAY_GIT_COMMIT_SHA).slice(0, 12)
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8', cwd: root }).trim()
  } catch {
    return `local-${Date.now()}`
  }
}

const buildId = resolveBuildId()
const payload = buildVersionManifest({ buildId })
const out = resolve(root, 'public/version.json')
writeFileSync(out, `${JSON.stringify(payload, null, 2)}\n`)
console.log(`Wrote ${out} (releaseLabel=${payload.releaseLabel}, buildId=${buildId})`)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { execSync } from 'node:child_process'

function resolveBuildId() {
  if (process.env.VITE_BUILD_ID) return String(process.env.VITE_BUILD_ID).slice(0, 64)
  if (process.env.VERCEL_GIT_COMMIT_SHA) return String(process.env.VERCEL_GIT_COMMIT_SHA).slice(0, 12)
  if (process.env.RAILWAY_GIT_COMMIT_SHA) return String(process.env.RAILWAY_GIT_COMMIT_SHA).slice(0, 12)
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
  } catch {
    return 'dev'
  }
}

const buildId = resolveBuildId()

// https://vite.dev/config/
export default defineConfig({
  define: {
    'import.meta.env.VITE_BUILD_ID': JSON.stringify(buildId),
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['branding/*.png'],
      manifest: false,
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,webmanifest}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
    {
      name: 'emit-version-json',
      closeBundle() {
        const payload = {
          buildId,
          builtAt: new Date().toISOString(),
        }
        writeFileSync(resolve('dist/version.json'), `${JSON.stringify(payload, null, 2)}\n`)
      },
    },
  ],
  server: {
    host: true,
    allowedHosts: true,
    headers: {
      'Permissions-Policy': 'geolocation=(self)',
    },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})

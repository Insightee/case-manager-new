import { defineConfig, devices } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(__dirname, '../backend')
const e2eDbPath = path.join(backendRoot, 'insightcase.e2e.db')
const e2eDatabaseUrl = process.env.PLAYWRIGHT_DATABASE_URL || `sqlite:///${e2eDbPath}`

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173'
const apiURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

const billingBackendEnv = {
  ENABLE_BILLING: 'true',
  BILLING_LEDGER_WRITES: 'false',
}

const billingFrontendEnv = {
  VITE_ENABLE_CLIENT_BILLING: 'true',
  VITE_ENABLE_BILLING: 'true',
  VITE_ENABLE_FINANCE_DASHBOARD_V1: 'true',
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER
    ? undefined
    : [
        {
          command: '../backend/scripts/e2e-dev-server.sh',
          url: `${apiURL}/health`,
          reuseExistingServer: false,
          timeout: 180_000,
          cwd: __dirname,
          env: {
            ...process.env,
            DATABASE_URL: e2eDatabaseUrl,
            RESET_E2E_DB: '1',
            ...billingBackendEnv,
          },
        },
        {
          command: 'npm run dev -- --host 127.0.0.1 --port 5173',
          url: baseURL,
          reuseExistingServer: false,
          timeout: 120_000,
          env: {
            ...process.env,
            ...billingFrontendEnv,
          },
        },
      ],
})

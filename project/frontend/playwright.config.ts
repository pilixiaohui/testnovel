import { defineConfig } from '@playwright/test'

const devPort = 5185
const devServerHost = process.env.VITE_DEV_SERVER_HOST || '127.0.0.2'
const devServerUrl = `http://${devServerHost}:${devPort}`

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 600000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: devServerUrl,
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host ${devServerHost} --port ${devPort} --strictPort`,
    url: devServerUrl,
    timeout: 600000,
    reuseExistingServer: false,
  },
})

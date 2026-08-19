import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'

const python = process.env.PYTHON || (existsSync('.venv/bin/python')
  ? '.venv/bin/python'
  : existsSync('.venv/Scripts/python.exe') ? '.venv/Scripts/python.exe' : 'python')

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'line',
  use: { baseURL: 'http://127.0.0.1:8191', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `${python} -m backend.app.run`,
    env: { ...process.env, PYTHONPATH: '.', LOCAL_AI_PORT: '8191', LOCAL_AI_DATA_DIR: '/tmp/local-ai-e2e' },
    url: 'http://127.0.0.1:8191/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})

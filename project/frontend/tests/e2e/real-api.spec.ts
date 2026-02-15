import { test, expect, type APIRequestContext } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const isRealApiMode = process.env.E2E_API_MODE === 'real'
const apiSourcePath = resolve(process.cwd(), 'src/api/index.ts')
const healthCheckPath = '/api/v1/health'
const healthCheckTimeoutMs = 6000
const requestTimeoutMs = 600000
let backendAvailable = false

const checkBackend = async (request: APIRequestContext) => {
  const response = await request.get(healthCheckPath, { timeout: healthCheckTimeoutMs })
  return response.status() < 500
}

test.describe('真实接口模式', () => {
  test.beforeAll(async ({ request }) => {
    if (!isRealApiMode) {
      return
    }

    try {
      backendAvailable = await checkBackend(request)
    } catch {
      backendAvailable = false
    }
  })

  test.beforeEach(() => {
    test.skip(!isRealApiMode, '需要真实后端，设置 E2E_API_MODE=real')
    test.skip(!backendAvailable, '后端不可用，跳过真实接口测试')
  })

  test('真实接口模式下请求可发出', async ({ page }) => {
    await page.goto('/snowflake')

    const step1Request = page.waitForRequest('**/api/v1/snowflake/step1')
    const step1Response = page.waitForResponse('**/api/v1/snowflake/step1', { timeout: requestTimeoutMs })
    await page.fill('[data-test="snowflake-idea-input"]', 'idea')
    await page.click('[data-test="snowflake-step1-submit"]')

    const request = await step1Request
    expect(request.url()).toContain('/api/v1/snowflake/step1')

    const response = await step1Response
    expect(response.status()).toBe(200)
  })

  test('前端 axios 超时配置为 600000ms', async () => {
    const source = readFileSync(apiSourcePath, 'utf8')
    expect(source).toContain('timeout: 600000')
  })
})

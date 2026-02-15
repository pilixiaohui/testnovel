import { test, expect, type Page } from '@playwright/test'
const jsonResponse = (data: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

const extractPreview = [
  {
    entity_id: 'e1',
    entity_name: 'Nova',
    confidence: 0.92,
    semantic_states_patch: {
      status: 'active',
      location: 'Harbor',
    },
    evidence: 'Chapter mentions Nova in Harbor.',
  },
]

const commitResult = {
  ok: true,
  root_id: 'root-alpha',
  branch_id: 'main',
  applied: 1,
  updated_entities: ['e1'],
}

const mockWorldRefreshApis = async (page: Page) => {
  await page.route('**/api/v1/roots/**/entities**', (route) =>
    route.fulfill(
      jsonResponse([
        {
          id: 'e1',
          name: 'Nova',
          type: 'character',
          position: { x: 0, y: 0, z: 0 },
        },
      ]),
    ),
  )
  await page.route('**/api/v1/roots/**/anchors**', (route) =>
    route.fulfill(jsonResponse(['Anchor One'])),
  )
  await page.route('**/api/v1/roots/**/subplots**', (route) =>
    route.fulfill(jsonResponse(['Subplot One'])),
  )
}

test('StateExtract 提取预览并提交更新世界', async ({ page }) => {
  await page.route('**/api/v1/state/extract', (route) => route.fulfill(jsonResponse(extractPreview)))
  await page.route('**/api/v1/state/commit**', (route) => route.fulfill(jsonResponse(commitResult)))
  await mockWorldRefreshApis(page)

  await page.goto('/editor/scene-alpha')
  await expect(page.locator('[data-test="state-extract"]')).toBeVisible()

  const extractRequest = page.waitForRequest('**/api/v1/state/extract')
  await page.click('[data-test="state-extract"]')
  await extractRequest

  const preview = page.locator('[data-test="state-extract-preview"]')
  await expect(preview).toBeVisible()
  await expect(preview).toContainText('Nova')

  const commitRequest = page.waitForRequest('**/api/v1/state/commit**')
  const entitiesRequest = page.waitForRequest('**/api/v1/roots/**/entities**')
  const anchorsRequest = page.waitForRequest('**/api/v1/roots/**/anchors**')
  const subplotsRequest = page.waitForRequest('**/api/v1/roots/**/subplots**')
  await page.click('[data-test="state-commit"]')
  await commitRequest
  await entitiesRequest
  await anchorsRequest
  await subplotsRequest

  await expect(page.locator('[data-test="state-commit-status"]')).toBeVisible()
})

test('StateExtract 失败后可重试', async ({ page }) => {
  let extractAttempts = 0
  let commitAttempts = 0

  await page.route('**/api/v1/state/extract', (route) => {
    extractAttempts += 1
    if (extractAttempts === 1) {
      route.fulfill(jsonResponse({ detail: 'extract failed' }, 500))
      return
    }
    route.fulfill(jsonResponse(extractPreview))
  })
  await page.route('**/api/v1/state/commit**', (route) => {
    commitAttempts += 1
    if (commitAttempts === 1) {
      route.fulfill(jsonResponse({ detail: 'commit failed' }, 500))
      return
    }
    route.fulfill(jsonResponse(commitResult))
  })
  await mockWorldRefreshApis(page)

  await page.goto('/editor/scene-alpha')

  await page.click('[data-test="state-extract"]')
  await expect(page.locator('[data-test="state-extract-error"]')).toBeVisible()

  await page.click('[data-test="state-extract-retry"]')
  await expect(page.locator('[data-test="state-extract-preview"]')).toBeVisible()

  await page.click('[data-test="state-commit"]')
  await expect(page.locator('[data-test="state-commit-error"]')).toBeVisible()

  await page.click('[data-test="state-commit-retry"]')
  await expect(page.locator('[data-test="state-commit-status"]')).toBeVisible()
})

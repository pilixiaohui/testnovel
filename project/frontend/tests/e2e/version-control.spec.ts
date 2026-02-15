import { test, expect } from '@playwright/test'
const jsonResponse = (data: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

test('VersionControl 分支列表与切换', async ({ page }) => {
  await page.route('**/api/v1/roots/*/branches', (route) =>
    route.fulfill(jsonResponse(['main', 'dev'])),
  )
  await page.route('**/api/v1/roots/*/branches/**/switch', (route) =>
    route.fulfill(jsonResponse({ root_id: 'root-alpha', branch_id: 'dev' })),
  )

  await page.goto('/editor')
  await expect(page.locator('[data-test="version-control-root"]')).toBeVisible()

  const branchList = page.locator('[data-test="branch-list"]')
  await expect(branchList).toContainText('main')
  await expect(branchList).toContainText('dev')

  await page.selectOption('[data-test="branch-switch-select"]', 'dev')
  const switchRequest = page.waitForRequest('**/api/v1/roots/*/branches/**/switch')
  await page.click('[data-test="branch-switch"]')
  await switchRequest

  await expect(page.locator('[data-test="branch-current"]')).toContainText('dev')
})

test('VersionControl 提交历史与快照操作', async ({ page }) => {
  await page.route('**/api/v1/roots/*/branches/**/history', (route) =>
    route.fulfill(
      jsonResponse([
        { id: 'commit-1', parent_id: null, message: 'Init', created_at: '2024-01-01' },
        { id: 'commit-2', parent_id: 'commit-1', message: 'Scene update', created_at: '2024-01-02' },
      ]),
    ),
  )
  await page.route('**/api/v1/roots/*', (route) =>
    route.fulfill(jsonResponse({ snapshot_seq: 10, entities: [{ id: 'e1', name: 'Nova' }] })),
  )
  await page.route('**/api/v1/roots/*/branches/**/reset', (route) =>
    route.fulfill(jsonResponse({ root_id: 'root-alpha', branch_id: 'main' })),
  )

  await page.goto('/editor')
  await expect(page.locator('[data-test="version-control-root"]')).toBeVisible()

  const historyRequest = page.waitForRequest('**/api/v1/roots/*/branches/**/history')
  await page.click('[data-test="commit-history-load"]')
  await historyRequest

  const historyList = page.locator('[data-test="commit-history-list"]')
  await expect(historyList).toContainText('commit-1')
  await expect(historyList).toContainText('commit-2')

  const snapshotRequest = page.waitForRequest('**/api/v1/roots/*')
  await page.click('[data-test="snapshot-load"]')
  await snapshotRequest

  await expect(page.locator('[data-test="snapshot-output"]')).toContainText('snapshot_seq')

  const restoreRequest = page.waitForRequest('**/api/v1/roots/*/branches/**/reset')
  await page.click('[data-test="snapshot-restore"]')
  await restoreRequest

  await expect(page.locator('[data-test="snapshot-restore-status"]')).toBeVisible()
})

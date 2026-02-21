import { expect, test } from '@playwright/test'
import {
  installWuxiaJourneyMocks,
  wuxiaChapters,
  wuxiaContext,
  wuxiaIdea,
  wuxiaLoglines,
  wuxiaRoot,
} from './helpers/wuxiaJourney'

test('WuxiaJourney: 十章武侠创作全链路端到端流程', async ({ page }) => {
  await installWuxiaJourneyMocks(page)

  await page.goto('/')
  await expect(page.locator('[data-test="home-view"]')).toBeVisible()

  await page.fill('[data-test="project-create-input"]', '江湖十章')
  await page.click('[data-test="create-project-btn"]')
  await page.waitForURL('**/snowflake')

  await expect(page.locator('[data-test="snowflake-flow-root"]')).toBeVisible()
  await expect(page.locator('[data-test="snowflake-prompt-controls"]')).toBeVisible()

  await page.fill('[data-test="snowflake-step1-prompt-input"]', '请写 10 条武侠一句话梗概')
  await page.click('[data-test="snowflake-prompt-save"]')

  await page.fill('[data-test="snowflake-idea-input"]', wuxiaIdea)
  await page.click('[data-test="snowflake-step1-submit"]')
  await expect(page.locator('[data-test="snowflake-logline-input"]')).toHaveCount(10)
  await expect(page.locator('[data-test="snowflake-step1-raw"]')).toContainText(wuxiaLoglines[0]!)

  await page.selectOption('[data-test="snowflake-logline-select"]', wuxiaLoglines[0]!)
  await page.click('[data-test="snowflake-step2-submit"]')
  await expect(page.locator('[data-test="snowflake-root-theme"]')).toContainText(wuxiaRoot.theme)

  await page.click('[data-test="snowflake-step3-submit"]')
  await expect(page.locator('[data-test="step3-character-details"]')).toContainText('沈孤舟')

  await page.click('[data-test="snowflake-step4-submit"]')
  await expect(page.locator('[data-test="step4-scene-details"] li')).toHaveCount(10)

  await page.click('[data-test="snowflake-step5-submit"]')
  await expect(page.locator('[data-test="step5-act-chapter-details"]')).toContainText('第10章')
  await expect(page.getByText('Acts: 2, Chapters: 10')).toBeVisible()

  await page.click('[data-test="snowflake-step6-submit"]')
  await page.waitForURL('**/editor**')
  await expect(page).toHaveURL(new RegExp(`root_id=${wuxiaContext.rootId}`))
  await expect(page).toHaveURL(new RegExp(`branch_id=${wuxiaContext.branchId}`))

  await expect(page.locator('[data-test="chapter-review-item"]')).toHaveCount(10)
  for (const chapter of wuxiaChapters) {
    const renderResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/v1/chapters/${chapter.id}/render`) &&
        response.request().method() === 'POST',
    )
    await page
      .locator('[data-test="chapter-review-item"]')
      .nth(chapter.sequence - 1)
      .locator('[data-test="chapter-render"]')
      .click()
    const renderPayload = (await (await renderResponsePromise).json()) as { rendered_content: string }
    const contentLength = renderPayload.rendered_content.replace(/\s/g, '').length
    expect(contentLength).toBeGreaterThanOrEqual(2000)
    expect(contentLength).toBeLessThanOrEqual(2205)
  }

  const firstChapter = page.locator('[data-test="chapter-review-item"]').first()
  await firstChapter.locator('[data-test="chapter-approve"]').click()
  await expect(firstChapter.locator('[data-test="chapter-review-status"]')).toContainText('approved')

  await page.click('[data-test="scene-load"]')
  await expect(page.locator('[data-test="scene-title-input"]')).toHaveValue('夜雨入城')
  await page.fill('[data-test="scene-summary-input"]', '沈孤舟在雨夜达成停战线索。')
  await page.selectOption('[data-test="scene-outcome-select"]', 'partial')
  await page.click('[data-test="scene-save"]')

  await page.click('[data-test="scene-diff"]')
  await expect(page.locator('[data-test="scene-diff-output"]')).toContainText('+ 新稿')
  await page.click('[data-test="scene-render"]')
  await expect(page.locator('[data-test="scene-render-output"]')).toContainText('渲染后场景正文')

  await page.click('[data-test="extract-state-btn"]')
  await expect(page.locator('[data-test="state-extract-preview"]')).toBeVisible()
  await page.click('[data-test="state-commit"]')
  await expect(page.locator('[data-test="state-commit-status"]')).toContainText('World updated.')

  await page.selectOption('[data-test="branch-switch-select"]', 'review')
  await page.click('[data-test="branch-switch"]')
  await expect(page.locator('[data-test="branch-current"]')).toContainText('review')
  await page.click('[data-test="commit-history-load"]')
  await expect(page.locator('[data-test="commit-history-list"]')).toContainText('commit-2')
  await page.click('[data-test="snapshot-load"]')
  await expect(page.locator('[data-test="snapshot-output"]')).toContainText('root_id')
  await page.click('[data-test="snapshot-restore"]')
  await expect(page.locator('[data-test="snapshot-restore-status"]')).toContainText('Snapshot restored.')

  await page.goto(
    `/simulation/${wuxiaContext.sceneId}?root_id=${wuxiaContext.rootId}&branch_id=${wuxiaContext.branchId}`,
  )
  await expect(page.locator('[data-test="simulation-console-root"]')).toBeVisible()
  await page.click('[data-test="simulation-start"]')
  await expect(page.locator('[data-test="simulation-log"] .log-line')).toHaveCount(1)
  await page.click('[data-test="simulation-step"]')
  await expect(page.locator('[data-test="simulation-converged"]')).toBeVisible()
  await page.click('[data-test="simulation-scene"]')
  await expect(page.locator('[data-test="simulation-log"] .log-line')).toHaveCount(3)

  await page.goto(`/world?root_id=${wuxiaContext.rootId}&branch_id=${wuxiaContext.branchId}`)
  await expect(page.locator('[data-test="world-manager-root"]')).toBeVisible()
  await page.click('[data-test="world-load"]')
  await expect(page.getByText('沈孤舟')).toBeVisible()
  await expect(page.getByText('沈孤舟与林晚晴的信任线')).toBeVisible()
  await page.click('[data-test="world-entity-create"]')
  await page.click('[data-test="world-entity-update"]')
  await page.click('[data-test="world-entity-delete"]')
  await page.click('[data-test="world-relations-show"]')
  await expect(page.locator('[data-test="world-relations-graph"]')).toContainText('source')

  await page.goto('/settings')
  await expect(page.locator('[data-test="settings-view-root"]')).toBeVisible()
  await page.fill('[data-test="settings-llm-model"]', 'gemini-wuxia-e2e')
  await page.click('[data-test="settings-save"]')
  await expect(page.locator('[data-test="settings-save-status"]')).toContainText('Saved at')
})

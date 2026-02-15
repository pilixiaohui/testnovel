import { test, expect, type Page } from '@playwright/test'
const jsonResponse = (data: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

const renderResult = {
  rendered_content: 'Rendered chapter content',
}

const mockChapterListApis = async (page: Page) => {
  await page.route('**/api/v1/roots/**/branches', (route) => route.fulfill(jsonResponse(['main'])))
  await page.route('**/api/v1/roots/**/acts', (route) =>
    route.fulfill(
      jsonResponse([
        {
          id: 'act-1',
          root_id: 'root-alpha',
          sequence: 1,
          title: 'Act One',
          purpose: 'Opening',
          tone: 'calm',
        },
      ]),
    ),
  )
  await page.route('**/api/v1/acts/**/chapters', (route) =>
    route.fulfill(
      jsonResponse([
        {
          id: 'ch-1',
          act_id: 'act-1',
          sequence: 1,
          title: 'Chapter One',
          focus: 'Introduction',
          review_status: 'pending',
        },
      ]),
    ),
  )
}

test('ChapterRender 渲染结果与质量评分', async ({ page }) => {
  await page.route('**/api/v1/chapters/**/render', (route) => route.fulfill(jsonResponse(renderResult)))
  await mockChapterListApis(page)

  await page.goto('/editor/scene-alpha')

  const chapterItem = page.locator('[data-test="chapter-review-item"]').first()
  await expect(chapterItem).toBeVisible()

  const renderRequest = page.waitForRequest('**/api/v1/chapters/**/render')
  await chapterItem.locator('[data-test="chapter-render"]').click()
  await renderRequest

  await expect(chapterItem.locator('[data-test="chapter-render-output"]')).toContainText('Rendered chapter content')
})

test('ChapterRender 失败后可重试', async ({ page }) => {
  let attempts = 0

  await page.route('**/api/v1/chapters/**/render', (route) => {
    attempts += 1
    if (attempts === 1) {
      route.fulfill(jsonResponse({ detail: 'render failed' }, 500))
      return
    }
    route.fulfill(jsonResponse(renderResult))
  })
  await mockChapterListApis(page)

  await page.goto('/editor/scene-alpha')

  const chapterItem = page.locator('[data-test="chapter-review-item"]').first()
  await expect(chapterItem).toBeVisible()

  await chapterItem.locator('[data-test="chapter-render"]').click()
  await expect(chapterItem.locator('[data-test="chapter-render-error"]')).toBeVisible()

  await chapterItem.locator('[data-test="chapter-render-retry"]').click()
  await expect(chapterItem.locator('[data-test="chapter-render-output"]')).toContainText('Rendered chapter content')
})

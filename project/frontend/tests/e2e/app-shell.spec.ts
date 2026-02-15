import { test, expect, type Page } from '@playwright/test'

const jsonResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

const trackPageErrors = (page: Page) => {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))
  return errors
}

const routeRoots = async (page: Page, fulfill: any) => {
  await page.route('**/api/v1/roots', (route) => route.fulfill(fulfill))
}

const expectHomeLayout = async (page: Page) => {
  await expect(page.locator('[data-test="home-view"]')).toBeVisible()
  await expect(page.locator('header.app-header')).toBeVisible()
}

test('Home 页面渲染基础布局', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(
    page,
    jsonResponse({
      roots: [],
    }),
  )

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots 缺失字段', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(page, jsonResponse({}))

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots 为 null', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(page, jsonResponse({ roots: null }))

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots API 返回 500', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(page, {
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({ message: 'mock 500' }),
  })

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots API 返回 204 空响应', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(page, {
    status: 204,
    body: '',
  })

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots API 返回非法 JSON', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(page, {
    status: 200,
    contentType: 'application/json',
    body: '{',
  })

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - roots API 延迟响应', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await page.route('**/api/v1/roots', async (route) => {
    await new Promise((r) => setTimeout(r, 500))
    await route.fulfill(
      jsonResponse({
        roots: [],
      }),
    )
  })

  await page.goto('/')

  await expectHomeLayout(page)
  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

test('Home 页面渲染 - 快速连续打开 3 次', async ({ page }) => {
  const pageErrors = trackPageErrors(page)
  await routeRoots(
    page,
    jsonResponse({
      roots: [],
    }),
  )

  for (let i = 0; i < 3; i++) {
    await page.goto('/')
    await expectHomeLayout(page)
  }

  await page.waitForTimeout(100)
  expect(pageErrors, `pageerror: ${pageErrors.join('\n')}`).toHaveLength(0)
})

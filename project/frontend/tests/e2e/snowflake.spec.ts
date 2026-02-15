import { test, expect, type Page } from '@playwright/test'
const jsonResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

const mockSnowflakeApis = async (page: Page) => {
  const loglines = ['A lone hero defies fate']
  const root = {
    logline: loglines[0],
    three_disasters: ['Storm', 'Betrayal', 'Sacrifice'],
    ending: 'Hope returns',
    theme: 'Courage',
  }

  await page.route('**/api/v1/snowflake/step1', (route) => route.fulfill(jsonResponse(loglines)))
  await page.route('**/api/v1/snowflake/step2', (route) => route.fulfill(jsonResponse(root)))
}

test('SnowflakeFlow 基本流程', async ({ page }) => {
  await mockSnowflakeApis(page)

  await page.goto('/snowflake')
  await expect(page.locator('[data-test="snowflake-flow-root"]')).toBeVisible()

  const stepList = page.locator('[data-test="snowflake-step-list"]')
  await expect(stepList).toBeVisible()
  await expect(stepList).toContainText('Step 1')

  const step1Request = page.waitForRequest('**/api/v1/snowflake/step1')
  await page.fill('[data-test="snowflake-idea-input"]', 'idea')
  await page.click('[data-test="snowflake-step1-submit"]')
  await step1Request
  const step1Panel = page.locator('section.step-panel').first()
  await expect(step1Panel.locator('li')).toContainText('A lone hero defies fate')

  const step2Request = page.waitForRequest('**/api/v1/snowflake/step2')
  await page.selectOption('[data-test="snowflake-logline-select"]', 'A lone hero defies fate')
  await page.click('[data-test="snowflake-step2-submit"]')
  await step2Request
  await expect(stepList).toContainText('Step 2 · Root (ready)')
})


const mockSnowflakeStep6Apis = async (page: Page) => {
  const loglines = ['A lone hero defies fate']
  const root = {
    logline: loglines[0],
    three_disasters: ['Storm', 'Betrayal', 'Sacrifice'],
    ending: 'Hope returns',
    theme: 'Courage',
  }
  const characters = [
    {
      id: 'c1',
      name: 'Nova',
      ambition: 'Protect the realm',
      conflict: 'Fear of failure',
      epiphany: 'Trust allies',
      voice_dna: 'steadfast',
    },
  ]
  const scenes = [
    {
      id: 's1',
      title: 'Hero faces the storm',
      sequence_index: 1,
      parent_act_id: 'act-1',
      chapter_id: 'ch-1',
      is_skeleton: true,
    },
  ]

  await page.route('**/api/v1/snowflake/step1', (route) => route.fulfill(jsonResponse(loglines)))
  await page.route('**/api/v1/snowflake/step2', (route) => route.fulfill(jsonResponse(root)))
  await page.route('**/api/v1/snowflake/step3', (route) => route.fulfill(jsonResponse(characters)))
  await page.route('**/api/v1/snowflake/step4', (route) =>
    route.fulfill(
      jsonResponse({
        root_id: 'root-alpha',
        branch_id: 'branch-1',
        scenes,
      }),
    ),
  )
  await page.route('**/api/v1/snowflake/step5a', (route) =>
    route.fulfill(jsonResponse([{ id: 'act-1' }])),
  )
  await page.route('**/api/v1/snowflake/step5b', (route) =>
    route.fulfill(
      jsonResponse([
        {
          id: 'ch-1',
          act_id: 'act-1',
          sequence: 1,
          title: 'Chapter One',
          focus: 'Introduce hero',
        },
      ]),
    ),
  )
  await page.route('**/api/v1/roots/**/anchors**', (route) =>
    route.fulfill(jsonResponse([{ id: 'anchor-1' }])),
  )
}

test('Snowflake Step6 完成后跳转 Editor', async ({ page }) => {
  await mockSnowflakeStep6Apis(page)

  await page.goto('/snowflake')
  await expect(page.locator('[data-test="snowflake-flow-root"]')).toBeVisible()

  const step1Request = page.waitForRequest('**/api/v1/snowflake/step1')
  await page.fill('[data-test="snowflake-idea-input"]', 'idea')
  await page.click('[data-test="snowflake-step1-submit"]')
  await step1Request

  const step2Request = page.waitForRequest('**/api/v1/snowflake/step2')
  await page.selectOption('[data-test="snowflake-logline-select"]', 'A lone hero defies fate')
  await page.click('[data-test="snowflake-step2-submit"]')
  await step2Request

  const step3Request = page.waitForRequest('**/api/v1/snowflake/step3')
  await page.click('[data-test="snowflake-step3-submit"]')
  await step3Request
  await expect(page.getByText('Nova')).toBeVisible()

  const step4Request = page.waitForRequest('**/api/v1/snowflake/step4')
  await page.click('[data-test="snowflake-step4-submit"]')
  await step4Request
  await expect(page.getByText('Hero faces the storm')).toBeVisible()

  const step5aRequest = page.waitForRequest('**/api/v1/snowflake/step5a')
  const step5bRequest = page.waitForRequest('**/api/v1/snowflake/step5b')
  await page.click('[data-test="snowflake-step5-submit"]')
  await step5aRequest
  await step5bRequest
  await expect(page.getByText('Acts: 1, Chapters: 1')).toBeVisible()

  const step6Request = page.waitForRequest('**/api/v1/roots/**/anchors**')
  await page.click('[data-test="snowflake-step6-submit"]')
  await step6Request

  await page.waitForURL('**/editor**')
  await expect(page).toHaveURL(/root_id=root-alpha/)
  await expect(page).toHaveURL(/branch_id=branch-1/)
})

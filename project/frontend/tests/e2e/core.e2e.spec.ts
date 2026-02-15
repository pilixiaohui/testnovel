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
  const characters = [
    {
      entity_id: 'c1',
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
      branch_id: 'b1',
      parent_act_id: null,
      pov_character_id: null,
      expected_outcome: 'Hero faces the storm',
      conflict_type: 'internal',
      actual_outcome: 'Resolve strengthened',
      logic_exception: false,
      is_dirty: false,
    },
  ]

  await page.route('**/api/v1/snowflake/step1', (route) => route.fulfill(jsonResponse(loglines)))
  await page.route('**/api/v1/snowflake/step2', (route) => route.fulfill(jsonResponse(root)))
  await page.route('**/api/v1/snowflake/step3', (route) => route.fulfill(jsonResponse(characters)))
  await page.route('**/api/v1/snowflake/step4', (route) =>
    route.fulfill(
      jsonResponse({
        root_id: 'root-alpha',
        branch_id: 'b1',
        scenes,
      }),
    ),
  )
  await page.route('**/api/v1/snowflake/step5a', (route) => route.fulfill(jsonResponse([{ id: 'act-1' }])))
  await page.route('**/api/v1/snowflake/step5b', (route) => route.fulfill(jsonResponse([{ id: 'ch-1' }])))
  await page.route('**/api/v1/roots/**/anchors**', (route) =>
    route.fulfill(jsonResponse([{ id: 'anchor-1' }])),
  )
}

const mockSimulationApis = async (page: Page) => {
  const config = {
    round_id: 'round-1',
    agent_actions: [],
    dm_arbitration: {
      round_id: 'round-1',
      action_results: [],
      conflicts_resolved: [],
      environment_changes: [],
    },
    narrative_events: [],
    sensory_seeds: [],
    convergence_score: 0,
    drama_score: 0,
    info_gain: 0,
    stagnation_count: 0,
  }

  await page.route('**/api/v1/simulation/logs/**', (route) => route.fulfill(jsonResponse([config])))
  await page.route('**/api/v1/simulation/round', (route) =>
    route.fulfill(jsonResponse({ convergence: true, status: 'running' })),
  )
  await page.route('**/api/v1/simulation/scene', (route) =>
    route.fulfill(jsonResponse({ status: 'running' })),
  )
}

const mockSceneApis = async (page: Page) => {
  await page.route('**/api/v1/scenes/**/context**', (route) =>
    route.fulfill(
      jsonResponse({
        id: 'scene-alpha',
        title: 'Opening',
        summary: 'A quiet village awakens',
        outcome: 'success',
      }),
    ),
  )
  await page.route('**/api/v1/scenes/**/render**', (route) =>
    route.fulfill(jsonResponse({ content: 'Rendered scene output' })),
  )
  await page.route('**/api/v1/scenes/**/diff**', (route) =>
    route.fulfill(jsonResponse({ diff: '-old\n+new' })),
  )
  await page.route('**/api/v1/scenes/**/complete**', (route) =>
    route.fulfill(jsonResponse({ status: 'ok' })),
  )
}

const mockWorldApis = async (page: Page) => {
  const entities = [
    {
      id: 'e1',
      created_at: '2024-01-01',
      name: 'Entity One',
      type: 'character',
      position: { x: 0, y: 0, z: 0 },
    },
    {
      id: 'e2',
      created_at: '2024-01-02',
      name: 'Entity Two',
      type: 'location',
      position: { x: 1, y: 1, z: 1 },
    },
  ]

  await page.route('**/api/v1/roots/**/entities**', (route) => route.fulfill(jsonResponse(entities)))
  await page.route('**/api/v1/roots/**/entities/**', (route) => route.fulfill(jsonResponse({ status: 'ok' })))
  await page.route('**/api/v1/roots/*', (route) =>
    route.fulfill(
      jsonResponse({
        relations: [{ from_entity_id: 'e1', to_entity_id: 'e2' }],
      }),
    ),
  )
  await page.route('**/api/v1/roots/**/anchors**', (route) => route.fulfill(jsonResponse(['Anchor One'])))
  await page.route('**/api/v1/roots/**/subplots**', (route) => route.fulfill(jsonResponse(['Subplot One'])))
}

test('SnowflakeFlow 核心流程', async ({ page }) => {
  await mockSnowflakeApis(page)

  await page.goto('/snowflake')
  await expect(page.locator('[data-test="snowflake-flow-root"]')).toBeVisible()

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
  await expect(page.locator('[data-test="snowflake-step-list"]')).toContainText('Step 2 · Root (ready)')

  const step3Request = page.waitForRequest('**/api/v1/snowflake/step3')
  await page.click('[data-test="snowflake-step3-submit"]')
  await step3Request
  await expect(page.getByText('Nova')).toBeVisible()

  const step4Request = page.waitForRequest('**/api/v1/snowflake/step4')
  await page.click('[data-test="snowflake-step4-submit"]')
  await step4Request
  await expect(page.getByText('Hero faces the storm')).toBeVisible()

  const step5Request = page.waitForRequest('**/api/v1/snowflake/step5a')
  await page.click('[data-test="snowflake-step5-submit"]')
  await step5Request
  await expect(page.getByText('Acts: 1, Chapters: 1')).toBeVisible()

  const step6Request = page.waitForRequest('**/api/v1/roots/**/anchors**')
  await page.click('[data-test="snowflake-step6-submit"]')
  await step6Request

  await page.waitForURL('**/editor**')
  await expect(page).toHaveURL(/root_id=root-alpha/)
  await expect(page).toHaveURL(/branch_id=b1/)
})

test('SimulationConsole 核心流程', async ({ page }) => {
  await mockSimulationApis(page)

  await page.goto('/simulation/scene-alpha')
  await expect(page.locator('[data-test="simulation-console-root"]')).toBeVisible()

  const loadRequest = page.waitForRequest('**/api/v1/simulation/logs/**')
  await page.click('[data-test="simulation-start"]')
  await loadRequest
  await expect(page.locator('[data-test="simulation-status"]')).toContainText('running')
  await expect(page.locator('[data-test="simulation-log"] .log-line')).toHaveCount(1)

  const roundRequest = page.waitForRequest('**/api/v1/simulation/round')
  await page.click('[data-test="simulation-step"]')
  await roundRequest
  await expect(page.locator('[data-test="simulation-converged"]')).toBeVisible()

  const sceneRequest = page.waitForRequest('**/api/v1/simulation/scene')
  await page.click('[data-test="simulation-scene"]')
  await sceneRequest
  await expect(page.locator('[data-test="simulation-log"] .log-line')).toHaveCount(3)
})

test('SceneEditor 核心流程', async ({ page }) => {
  await mockSceneApis(page)

  await page.goto('/editor/scene-alpha')
  await expect(page.locator('[data-test="scene-editor-root"]')).toBeVisible()

  const contextRequest = page.waitForResponse('**/api/v1/scenes/**/context**')
  const renderRequest = page.waitForResponse('**/api/v1/scenes/**/render**')
  await page.click('[data-test="scene-load"]')
  await contextRequest
  await renderRequest
  await expect(page.locator('[data-test="scene-title-input"]')).toHaveValue('Opening')
  await expect(page.locator('[data-test="scene-summary-input"]')).toHaveValue('A quiet village awakens')

  await page.fill('[data-test="scene-summary-input"]', 'Updated summary')
  await page.selectOption('[data-test="scene-outcome-select"]', 'partial')
  await expect(page.locator('[data-test="scene-dirty"]')).toBeVisible()

  const updateRequest = page.waitForRequest('**/api/v1/scenes/**/complete**')
  await page.click('[data-test="scene-save"]')
  await updateRequest
  await expect(page.locator('[data-test="scene-dirty"]')).toHaveCount(0)

  const diffRequest = page.waitForRequest('**/api/v1/scenes/**/diff**')
  await page.click('[data-test="scene-diff"]')
  await diffRequest
  await expect(page.locator('[data-test="scene-diff-output"]')).toContainText('+new')
  await expect(page.locator('[data-test="scene-dirty"]')).toBeVisible()

  const renderRequestAgain = page.waitForResponse('**/api/v1/scenes/**/render**')
  await page.click('[data-test="scene-render"]')
  await renderRequestAgain
  await expect(page.locator('[data-test="scene-render-output"]')).toContainText('Rendered scene output')
})

test('WorldManager 核心流程', async ({ page }) => {
  await mockWorldApis(page)

  await page.goto('/world')
  await expect(page.locator('[data-test="world-manager-root"]')).toBeVisible()

  const entitiesRequest = page.waitForRequest('**/api/v1/roots/**/entities**')
  const anchorsRequest = page.waitForRequest('**/api/v1/roots/**/anchors**')
  const subplotsRequest = page.waitForRequest('**/api/v1/roots/**/subplots**')
  await page.click('[data-test="world-load"]')
  await entitiesRequest
  await anchorsRequest
  await subplotsRequest
  await expect(page.getByText('Entity One')).toBeVisible()
  await expect(page.getByText('Anchor One')).toBeVisible()
  await expect(page.getByText('Subplot One')).toBeVisible()

  const createRequest = page.waitForRequest('**/api/v1/roots/**/entities**')
  await page.click('[data-test="world-entity-create"]')
  await createRequest

  const updateRequest = page.waitForRequest('**/api/v1/roots/**/entities/**')
  await page.click('[data-test="world-entity-update"]')
  await updateRequest

  const deleteRequest = page.waitForRequest('**/api/v1/roots/**/entities/**')
  await page.click('[data-test="world-entity-delete"]')
  await deleteRequest

  const relationsRequest = page.waitForRequest('**/api/v1/roots/*')
  await page.click('[data-test="world-relations-show"]')
  await relationsRequest
  await expect(page.locator('[data-test="world-relations-graph"]')).toBeVisible()
  await expect(page.locator('[data-test="world-relations-graph"]')).toContainText('"source"')
})

test('Settings 保存流程', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.locator('[data-test="settings-view-root"]')).toBeVisible()
  await expect(page.locator('[data-test="settings-save"]')).toBeVisible()
})


test('ChapterReview 审核更新状态', async ({ page }) => {
  await expect(page.locator('html')).toBeVisible()
  await page.route('**/api/v1/chapters/**/review', (route) =>
    route.fulfill(jsonResponse({ id: 'ch-1', review_status: 'approved' })),
  )
  await page.route('**/api/v1/roots/*/branches', (route) => route.fulfill(jsonResponse(['main'])))
  await page.route('**/api/v1/roots/*/acts', (route) =>
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

  await page.goto('/editor/scene-alpha')

  const chapterItem = page.locator('[data-test="chapter-review-item"]').first()
  await expect(chapterItem).toBeVisible()

  const reviewRequest = page.waitForRequest('**/api/v1/chapters/**/review')
  await chapterItem.locator('[data-test="chapter-approve"]').click()
  await reviewRequest

  await expect(chapterItem.locator('[data-test="chapter-review-status"]')).toContainText('approved')
})

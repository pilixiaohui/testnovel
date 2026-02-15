import { test, expect, type Page } from '@playwright/test'
const jsonResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(data),
})

const mockSimulationApis = async (page: Page) => {
  const config = {
    round_id: 'round-1',
    agent_actions: [
      {
        agent_id: 'agent-1',
        internal_thought: 'Assess situation',
        action_type: 'observe',
        action_target: 'area',
        dialogue: '',
        action_description: 'Scanning the environment',
      },
    ],
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
    info_gain: 1,
    stagnation_count: 0,
  }

  await page.route('**/api/v1/simulation/logs/**', (route) => route.fulfill(jsonResponse([config])))
}

test('SimulationConsole 基本流程', async ({ page }) => {
  await mockSimulationApis(page)

  await page.goto('/simulation')
  await expect(page.locator('[data-test="simulation-console-root"]')).toBeVisible()

  await expect(page.locator('[data-test="simulation-start"]')).toBeVisible()
  await expect(page.locator('[data-test="simulation-stop"]')).toBeVisible()
  await expect(page.locator('[data-test="simulation-reset"]')).toBeVisible()

  await expect(page.locator('[data-test="simulation-agent-state"]')).toBeVisible()

  const loadRequest = page.waitForRequest('**/api/v1/simulation/logs/**')
  await page.click('[data-test="simulation-start"]')
  await loadRequest

  await expect(page.locator('[data-test="simulation-round-player"]')).toBeVisible()
  await expect(page.getByRole('button', { name: '播放' })).toBeVisible()
  await expect(page.locator('[data-test="simulation-timeline"]')).toBeVisible()
  await expect(page.getByText('Action Timeline')).toBeVisible()
})

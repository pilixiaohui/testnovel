// Playwright MCP E2E test plan skeleton.
// NOTE: This is a plan-only file for design mode; real execution uses MCP flows.

export const e2eSelectors = {
  snowflakeFlow: {
    root: '[data-test="snowflake-flow-root"]',
    stepList: '[data-test="snowflake-step-list"]',
    addStep: '[data-test="snowflake-add-step"]',
  },
  simulationConsole: {
    root: '[data-test="simulation-console-root"]',
    status: '[data-test="simulation-status"]',
    log: '[data-test="simulation-log"]',
    start: '[data-test="simulation-start"]',
    stop: '[data-test="simulation-stop"]',
  },
  sceneEditor: {
    root: '[data-test="scene-editor-root"]',
    form: '[data-test="scene-editor-form"]',
    titleInput: '[data-test="scene-title-input"]',
    save: '[data-test="scene-save"]',
  },
  worldManager: {
    root: '[data-test="world-manager-root"]',
    list: '[data-test="world-list"]',
    create: '[data-test="world-create"]',
  },
  settings: {
    root: '[data-test="settings-root"]',
    save: '[data-test="settings-save"]',
  },
} as const

export const e2eScenarios = [
  'SnowflakeFlow: add step and verify list length increments',
  'SimulationConsole: start -> status running -> stop -> status stopped',
  'SceneEditor: fill title -> save -> success indicator appears',
  'WorldManager: create world -> appears in list',
  'Settings: update config -> save -> success indicator appears',
] as const

throw new Error('E2E plan-only file: execute flows via Playwright MCP')

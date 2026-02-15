import './element_plus_style_mock'
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SnowflakeView from '../src/views/SnowflakeView.vue'
import SimulationView from '../src/views/SimulationView.vue'
import EditorView from '../src/views/EditorView.vue'
import WorldView from '../src/views/WorldView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { sceneId: 'scene-alpha' },
    query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn().mockResolvedValue({ scenes: [] }),
  fetchSceneContext: vi.fn().mockResolvedValue({ id: 'scene-alpha' }),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulations: vi.fn(),
  fetchSimulationAgents: vi.fn().mockResolvedValue({ agents: [] }),
  runRound: vi.fn(),
  runScene: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  fetchAgents: vi.fn().mockResolvedValue([]),
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn().mockResolvedValue(['main']),
  },
}))

vi.mock('@/api/snowflake', () => ({
  snowflakeApi: {
    listActs: vi.fn().mockResolvedValue([]),
    listChapters: vi.fn().mockResolvedValue([]),
  },
}))

const mountView = (component: unknown, options: Parameters<typeof mount>[1] = {}) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(component as Record<string, unknown>, {
    ...options,
    global: {
      ...options.global,
      plugins: [...(options.global?.plugins || []), pinia],
    },
  })
}

describe('M1-T2 core views minimal', () => {
  it('SnowflakeView exposes minimal layout and actions', () => {
    const wrapper = mountView(SnowflakeView)
    expect(wrapper.get('h1').text()).toBe('Snowflake Flow')
    expect(wrapper.find('[data-test="snowflake-step-list"]').exists()).toBe(true)
    const addButton = wrapper.find('[data-test="snowflake-add-step"]')
    expect(addButton.exists()).toBe(true)
    expect(addButton.element.tagName).toBe('BUTTON')
  })

  it('SimulationView exposes status, controls, and output', () => {
    const wrapper = mountView(SimulationView)
    expect(wrapper.get('h1').text()).toBe('Simulation Console')
    expect(wrapper.find('[data-test="simulation-status"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="simulation-log"]').exists()).toBe(true)
    const startButton = wrapper.find('[data-test="simulation-start"]')
    const stopButton = wrapper.find('[data-test="simulation-stop"]')
    expect(startButton.exists()).toBe(true)
    expect(stopButton.exists()).toBe(true)
    expect(startButton.element.tagName).toBe('BUTTON')
    expect(stopButton.element.tagName).toBe('BUTTON')
  })

  it('EditorView exposes editor form and save action', () => {
    const wrapper = mountView(EditorView)
    expect(wrapper.get('h1').text()).toBe('Scene Editor')
    expect(wrapper.find('[data-test="scene-editor-form"]').exists()).toBe(true)
    const titleInput = wrapper.find('[data-test="scene-title-input"]')
    expect(titleInput.exists()).toBe(true)
    expect(['INPUT', 'TEXTAREA']).toContain(titleInput.element.tagName)
    const saveButton = wrapper.find('[data-test="scene-save"]')
    expect(saveButton.exists()).toBe(true)
    expect(saveButton.element.tagName).toBe('BUTTON')
  })

  it('WorldView exposes world list and create action', () => {
    const wrapper = mountView(WorldView)
    expect(wrapper.get('h1').text()).toBe('World Manager')
    expect(wrapper.find('[data-test="world-list"]').exists()).toBe(true)
    const createButton = wrapper.find('[data-test="world-create"]')
    expect(createButton.exists()).toBe(true)
    expect(createButton.element.tagName).toBe('BUTTON')
  })
})

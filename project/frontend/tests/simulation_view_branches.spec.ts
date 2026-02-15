import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useSimulationStore } from '@/stores/simulation'
import SimulationView from '../src/views/SimulationView.vue'
import * as sceneApi from '@/api/scene'
import * as simulationApi from '@/api/simulation'
import * as agentApi from '@/api/agent'

const routeState = vi.hoisted(() => ({
  params: { sceneId: '' as string | undefined, rootId: undefined as string | undefined, branchId: undefined as string | undefined },
  query: {} as Record<string, string | undefined>,
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulations: vi.fn(),
  fetchSimulationAgents: vi.fn(),
  runRound: vi.fn(),
  runScene: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
}

const simulationApiMock = vi.mocked(simulationApi) as unknown as {
  fetchSimulations: ReturnType<typeof vi.fn>
  fetchSimulationAgents: ReturnType<typeof vi.fn>
  runRound: ReturnType<typeof vi.fn>
  runScene: ReturnType<typeof vi.fn>
}

const agentApiMock = vi.mocked(agentApi) as unknown as {
  agentApi: {
    getAgentState: ReturnType<typeof vi.fn>
  }
}

const mountSimulation = (options: {
  sceneId?: string
  rootId?: string
  branchId?: string
  sceneStoreId?: string
  ensureProject?: boolean
} = {}) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  if (options.ensureProject) {
    projectStore.setCurrentProject(options.rootId || 'root-alpha', options.branchId || 'main', options.sceneStoreId || '')
  } else {
    projectStore.root_id = options.rootId || ''
    projectStore.branch_id = options.branchId || ''
    projectStore.scene_id = options.sceneStoreId || ''
  }

  routeState.params.sceneId = options.sceneId
  routeState.params.rootId = options.rootId
  routeState.params.branchId = options.branchId
  routeState.query = {}

  const wrapper = mount(SimulationView, {
    global: {
      plugins: [pinia],
      stubs: {
        ActionTimeline: true,
        AgentStatePanel: true,
        RoundPlayer: true,
      },
    },
  })
  const simulationStore = useSimulationStore()
  return { wrapper, projectStore, simulationStore }
}

describe('SimulationView branches', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = ''
    routeState.params.rootId = undefined
    routeState.params.branchId = undefined
    routeState.query = {}
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    sceneApiMock.fetchSceneContext.mockResolvedValue({ data: { summary: 'context', scene_id: 'scene-alpha' } })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-1',
      character_id: 'Nova',
      branch_id: 'main',
      beliefs: {},
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 1,
      version: 1,
    })
    simulationApiMock.fetchSimulations.mockResolvedValue([])
    simulationApiMock.runRound.mockResolvedValue({})
    simulationApiMock.runScene.mockResolvedValue({ status: 'running' })
  })

  it('shows empty state when scene id is missing', async () => {
    const { wrapper } = mountSimulation({ sceneId: '', rootId: '', branchId: '' })

    await flushPromises()

    expect(wrapper.find('[data-test="simulation-empty"]').exists()).toBe(true)
    expect(sceneApiMock.fetchSceneContext).not.toHaveBeenCalled()
    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()

    const startButton = wrapper.find('[data-test="simulation-start"]')
    const runButton = wrapper.find('[data-test="run-simulation-btn"]')
    const resultsPanel = wrapper.find('[data-test="simulation-results"]')
    expect(startButton.attributes('disabled')).toBeDefined()
    expect(runButton.attributes('disabled')).toBeDefined()
    expect(resultsPanel.exists()).toBe(true)
  })

  it('starts simulation and renders rounds on success', async () => {
    expect(simulationApiMock.fetchSimulations).not.toHaveBeenCalled()
    simulationApiMock.fetchSimulations.mockResolvedValue([
      {
        round_id: 'r1',
        agent_actions: [],
        dm_arbitration: {
          round_id: 'r1',
          action_results: [],
          conflicts_resolved: [],
          environment_changes: [],
        },
        narrative_events: [],
        sensory_seeds: [],
        convergence_score: 0.1,
        drama_score: 0.1,
        info_gain: 0.2,
        stagnation_count: 0,
      },
    ])

    const { wrapper } = mountSimulation({ sceneId: 'scene-alpha', rootId: 'root-alpha', branchId: 'main', ensureProject: true })

    await flushPromises()

    const startButton = wrapper.find('[data-test="simulation-start"]')
    await startButton.trigger('click')
    await flushPromises()

    expect(simulationApiMock.fetchSimulations).toHaveBeenCalledWith('scene-alpha')
    expect(wrapper.find('[data-test="simulation-rounds"]').exists()).toBe(true)
    expect(wrapper.findAll('.log-line').length).toBeGreaterThan(0)
  })

  it('keeps pending log when start fails', async () => {
    simulationApiMock.fetchSimulations.mockRejectedValue(new Error('failed'))

    const { wrapper } = mountSimulation({ sceneId: 'scene-beta', rootId: 'root-alpha', branchId: 'main', ensureProject: true })

    await flushPromises()

    const startButton = wrapper.find('[data-test="simulation-start"]')
    await startButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Loading simulations')
    expect(wrapper.find('[data-test="simulation-rounds"]').exists()).toBe(false)
  })

  it('steps simulation and converges by score', async () => {
    expect(simulationApiMock.runRound).not.toHaveBeenCalled()
    sceneApiMock.fetchSceneContext.mockResolvedValue(JSON.stringify({ data: { summary: 'ctx', scene_id: 'scene-gamma' } }))
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [
      {
        id: 'agent-1',
        character_id: 'Nova',
        branch_id: '',
        beliefs: { mood: 'curious' },
        desires: [],
        intentions: [],
        memory: [],
        private_knowledge: [],
        last_updated_scene: 0,
        version: 1,
      },
    ] })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-1',
      character_id: 'Nova',
      branch_id: 'main',
      beliefs: { mood: 'curious' },
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 0,
      version: 1,
    })
    simulationApiMock.runRound.mockResolvedValue({ round_id: 'round-1', convergence_score: 0.9 })

    const { wrapper } = mountSimulation({ sceneId: 'scene-gamma', rootId: 'root-alpha', branchId: 'main', ensureProject: true })

    await flushPromises()

    const stepButton = wrapper.find('[data-test="simulation-step"]')
    await stepButton.trigger('click')
    await flushPromises()

    expect(simulationApiMock.runRound).toHaveBeenCalled()
    expect(wrapper.find('[data-test="simulation-converged"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="simulation-rounds"]').exists()).toBe(true)
  })

  it('steps simulation and converges by legacy flag without round id', async () => {
    expect(simulationApiMock.runRound).not.toHaveBeenCalled()
    sceneApiMock.fetchSceneContext.mockResolvedValue({ summary: 'ctx', scene_id: 'scene-delta' })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [
      {
        id: 'agent-2',
        character_id: 'Echo',
        branch_id: 'main',
        beliefs: 'unknown',
        desires: 'invalid',
        intentions: 'invalid',
        memory: 'invalid',
        private_knowledge: 'invalid',
        last_updated_scene: 'invalid',
        version: 'invalid',
      },
    ] })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-2',
      character_id: 'Echo',
      branch_id: 'main',
      beliefs: {},
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 0,
      version: 1,
    })
    simulationApiMock.runRound.mockResolvedValue({ convergence: true })

    const { wrapper } = mountSimulation({ sceneId: 'scene-delta', rootId: 'root-alpha', branchId: 'main', ensureProject: true })

    await flushPromises()

    const stepButton = wrapper.find('[data-test="simulation-step"]')
    await stepButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="simulation-converged"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="simulation-rounds"]').exists()).toBe(false)
  })

  it('runs scene simulation and supports stop/reset', async () => {
    const { wrapper, simulationStore } = mountSimulation({ sceneId: 'scene-epsilon', rootId: 'root-alpha', branchId: 'main', ensureProject: true })

    await flushPromises()

    const sceneButton = wrapper.find('[data-test="run-simulation-btn"]')
    await sceneButton.trigger('click')
    await flushPromises()

    expect(simulationApiMock.runScene).toHaveBeenCalled()

    simulationStore.setStatus('running')

    const stopButton = wrapper.find('[data-test="simulation-stop"]')
    await stopButton.trigger('click')
    expect(simulationStore.status).toBe('idle')

    const resetButton = wrapper.find('[data-test="simulation-reset"]')
    await resetButton.trigger('click')
    expect(simulationStore.status).toBe('idle')
  })
})

import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import * as simulationApi from '@/api/simulation'
import * as sceneApi from '@/api/scene'
import * as agentApi from '@/api/agent'
import SimulationView from '../src/views/SimulationView.vue'

const routeState = vi.hoisted(() => ({
  params: { sceneId: 'scene-alpha01' },
  query: { root_id: 'root-alpha01', branch_id: 'main' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulations: vi.fn(),
  runRound: vi.fn(),
  runScene: vi.fn(),
  fetchSimulationAgents: vi.fn(),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

const simulationApiMock = vi.mocked(simulationApi) as unknown as {
  fetchSimulations: ReturnType<typeof vi.fn>
  runRound: ReturnType<typeof vi.fn>
  runScene: ReturnType<typeof vi.fn>
  fetchSimulationAgents: ReturnType<typeof vi.fn>
}

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
}

const agentApiMock = vi.mocked(agentApi) as unknown as {
  agentApi: {
    getAgentState: ReturnType<typeof vi.fn>
  }
}

const mountSimulationView = (options: {
  rootId?: string
  branchId?: string
  sceneId?: string
} = {}) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  const resolvedRootId = options.rootId ?? 'root-alpha01'
  const resolvedBranchId = options.branchId ?? 'main'
  const resolvedSceneId = options.sceneId ?? 'scene-alpha01'

  projectStore.root_id = resolvedRootId
  projectStore.branch_id = resolvedBranchId
  projectStore.scene_id = resolvedSceneId

  routeState.params.sceneId = resolvedSceneId
  routeState.query = { root_id: resolvedRootId, branch_id: resolvedBranchId }

  return mount(SimulationView, { global: { plugins: [pinia] } })
}

describe('M1-T5 simulation context contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params.sceneId = 'scene-alpha01'
    routeState.query = { root_id: 'root-alpha01', branch_id: 'main' }
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
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
  })

  it('test_SimulationView_loads_real_scene_context', async () => {
    const sceneId = routeState.params.sceneId
    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: sceneId, summary: 'Loaded' })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })

    mountSimulationView()
    await flushPromises()

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalled()
    const [calledSceneId] = sceneApiMock.fetchSceneContext.mock.calls[0] || []
    expect(calledSceneId).toBe(sceneId)
  })

  it('test_SimulationView_loads_real_agents', async () => {
    expect(routeState.params.sceneId).toBe('scene-alpha01')
    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: routeState.params.sceneId })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({
      agents: [
        {
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
        },
      ],
    })
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

    mountSimulationView()
    await flushPromises()

    expect(simulationApiMock.fetchSimulationAgents).toHaveBeenCalled()
    const [calledRootId, calledBranchId] =
      simulationApiMock.fetchSimulationAgents.mock.calls[0] || []
    expect(calledRootId).toBe('root-alpha01')
    expect(calledBranchId).toBe('main')
    expect(agentApiMock.agentApi.getAgentState).toHaveBeenCalledWith('agent-1', 'main')
  })

  it('test_runRound_payload_not_empty', async () => {
    const sceneId = routeState.params.sceneId
    const agents = [{ id: 'agent-1', character_id: 'Nova' }]
    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: sceneId, summary: 'Loaded' })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents })
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
    simulationApiMock.runRound.mockResolvedValue({ status: 'running', convergence_score: 0.2 })

    const wrapper = mountSimulationView()
    await flushPromises()

    const stepButton = wrapper.find('[data-test="simulation-step"]')
    expect(stepButton.exists()).toBe(true)
    await stepButton.trigger('click')
    await flushPromises()

    expect(simulationApiMock.runRound).toHaveBeenCalled()
    const payload = simulationApiMock.runRound.mock.calls[0]?.[0] as {
      scene_context?: Record<string, unknown>
      agents?: Array<Record<string, unknown>>
    }
    expect(payload.scene_context).toBeDefined()
    if (!payload.scene_context) {
      throw new Error('scene_context is required in runRound payload')
    }
    expect(Object.keys(payload.scene_context).length).toBeGreaterThan(0)
    expect(Array.isArray(payload.agents)).toBe(true)
    expect(payload.agents?.length).toBeGreaterThan(0)
  })

  it('test_no_hardcoded_scene_id', async () => {
    const sceneId = 'scene-dynamic-777'
    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: sceneId })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })

    mountSimulationView({ sceneId })
    await flushPromises()

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalled()
    const [calledSceneId] = sceneApiMock.fetchSceneContext.mock.calls[0] || []
    expect(calledSceneId).toBe(sceneId)
  })
})

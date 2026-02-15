import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import SimulationView from '../src/views/SimulationView.vue'
import * as sceneApi from '@/api/scene'
import * as simulationApi from '@/api/simulation'
import * as agentApi from '@/api/agent'

const routeState = vi.hoisted(() => ({
  params: {
    sceneId: 'scene-alpha' as string | undefined,
    rootId: undefined as string | undefined,
    branchId: undefined as string | undefined,
  },
  query: {
    root_id: 'root-route',
    branch_id: 'branch-route',
  } as Record<string, string | undefined>,
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
  runRound: vi.fn(),
  runScene: vi.fn(),
  fetchSimulationAgents: vi.fn(),
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
  runRound: ReturnType<typeof vi.fn>
  runScene: ReturnType<typeof vi.fn>
  fetchSimulationAgents: ReturnType<typeof vi.fn>
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
  routeQuery?: Record<string, string | undefined>
} = {}) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  const hasRootId = Object.prototype.hasOwnProperty.call(options, 'rootId')
  const hasBranchId = Object.prototype.hasOwnProperty.call(options, 'branchId')
  const hasSceneId = Object.prototype.hasOwnProperty.call(options, 'sceneId')
  const resolvedRootId = hasRootId ? options.rootId ?? '' : 'root-store'
  const resolvedBranchId = hasBranchId ? options.branchId ?? '' : 'branch-store'
  const resolvedSceneId = hasSceneId ? options.sceneId ?? '' : 'scene-alpha'

  projectStore.root_id = resolvedRootId
  projectStore.branch_id = resolvedBranchId
  projectStore.scene_id = resolvedSceneId

  routeState.params.sceneId = resolvedSceneId
  routeState.query = options.routeQuery ?? {
    root_id: 'root-route',
    branch_id: 'branch-route',
  }

  const wrapper = mount(SimulationView, {
    global: {
      plugins: [pinia],
      stubs: {
        ActionTimeline: true,
        AgentStatePanel: true,
        RoundPlayer: true,
        ConvergenceIndicator: true,
      },
    },
  })

  return { wrapper, projectStore }
}

const loadAgentsManually = async (wrapper: ReturnType<typeof mount>) => {
  await (wrapper.vm as unknown as { loadAgents: () => Promise<void> }).loadAgents()
  await flushPromises()
}

const expectMissingContextState = (wrapper: ReturnType<typeof mount>) => {
  const hasError = wrapper.find('[data-test="simulation-error"]').exists()
  const hasEmpty = wrapper.find('[data-test="simulation-agents-empty"]').exists()
  const hasContext = wrapper.find('[data-test="simulation-context-missing"]').exists()
  expect(hasError || hasEmpty || hasContext).toBe(true)
}

const runSceneAndGetPayload = async (wrapper: ReturnType<typeof mount>) => {
  await wrapper.find('[data-test="simulation-scene"]').trigger('click')
  await flushPromises()
  const [payload] = simulationApiMock.runScene.mock.calls[0] || []
  return payload as { scene_context?: { scene_id?: string } } | undefined
}

describe('M3-T1 SimulationView real agent state + convergence indicator', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = 'scene-alpha'
    routeState.query = { root_id: 'root-route', branch_id: 'branch-route' }
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    sceneApiMock.fetchSceneContext.mockResolvedValue({ data: { summary: 'context', scene_id: 'scene-alpha' } })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-1',
      character_id: 'Nova',
      branch_id: 'branch-store',
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

  it('M3-T1 loads agent state from simulation API using project store context', async () => {
    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({
      agents: [
        {
          id: 'agent-1',
          character_id: 'Nova',
          branch_id: 'branch-store',
          beliefs: { mood: 'focused' },
          desires: [],
          intentions: [],
          memory: [],
          private_knowledge: {},
          last_updated_scene: 2,
          version: 1,
        },
      ],
      convergence: {
        score: 0.42,
        check: {
          next_anchor_id: 'anchor-1',
          distance: 0.3,
          convergence_needed: false,
        },
      },
    })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-1',
      character_id: 'Nova',
      branch_id: 'branch-store',
      beliefs: { mood: 'focused' },
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 2,
      version: 1,
    })

    const { wrapper } = mountSimulationView({
      rootId: 'root-store',
      branchId: 'branch-store',
      sceneId: 'scene-alpha',
    })

    await flushPromises()

    expect(simulationApiMock.fetchSimulationAgents).toHaveBeenCalled()
    const [calledRootId, calledBranchId] = simulationApiMock.fetchSimulationAgents.mock.calls[0] || []
    expect(calledRootId).toBe('root-store')
    expect(calledBranchId).toBe('branch-store')
    expect(agentApiMock.agentApi.getAgentState).toHaveBeenCalledWith('agent-1', 'branch-store')
    expect(wrapper.find('[data-test="simulation-agent-state"]').exists()).toBe(true)
  })

  it('M3-T1 uses store context when route query is empty', async () => {
    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({
      agents: [
        {
          id: 'agent-3',
          character_id: 'Lumen',
          branch_id: 'branch-store',
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
      id: 'agent-3',
      character_id: 'Lumen',
      branch_id: 'branch-store',
      beliefs: {},
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 1,
      version: 1,
    })

    mountSimulationView({
      rootId: 'root-store',
      branchId: 'branch-store',
      sceneId: 'scene-alpha',
      routeQuery: {},
    })

    await flushPromises()

    expect(simulationApiMock.fetchSimulationAgents).toHaveBeenCalled()
    const [calledRootId, calledBranchId] = simulationApiMock.fetchSimulationAgents.mock.calls[0] || []
    expect(calledRootId).toBe('root-store')
    expect(calledBranchId).toBe('branch-store')
  })

  it('M3-T1 uses store context when route root_id is empty string', async () => {
    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({
      agents: [
        {
          id: 'agent-4',
          character_id: 'Sol',
          branch_id: 'branch-store',
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
      id: 'agent-4',
      character_id: 'Sol',
      branch_id: 'branch-store',
      beliefs: {},
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 1,
      version: 1,
    })

    mountSimulationView({
      rootId: 'root-store',
      branchId: 'branch-store',
      sceneId: 'scene-alpha',
      routeQuery: { root_id: '' },
    })

    await flushPromises()

    expect(simulationApiMock.fetchSimulationAgents).toHaveBeenCalled()
    const [calledRootId, calledBranchId] = simulationApiMock.fetchSimulationAgents.mock.calls[0] || []
    expect(calledRootId).toBe('root-store')
    expect(calledBranchId).toBe('branch-store')
  })

  it('M3-T1 renders convergence indicator with API data', async () => {
    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    const convergencePayload = {
      score: 0.88,
      check: {
        next_anchor_id: 'anchor-9',
        distance: 0.2,
        convergence_needed: false,
      },
    }

    simulationApiMock.fetchSimulationAgents.mockResolvedValue({
      agents: [
        {
          id: 'agent-2',
          character_id: 'Echo',
          branch_id: 'branch-store',
          beliefs: {},
          desires: [],
          intentions: [],
          memory: [],
          private_knowledge: {},
          last_updated_scene: 1,
          version: 1,
        },
      ],
      convergence: convergencePayload,
    })
    agentApiMock.agentApi.getAgentState.mockResolvedValue({
      id: 'agent-2',
      character_id: 'Echo',
      branch_id: 'branch-store',
      beliefs: {},
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 1,
      version: 1,
    })

    const { wrapper } = mountSimulationView()

    await flushPromises()

    const indicator = wrapper.findComponent({ name: 'ConvergenceIndicator' })
    expect(indicator.exists()).toBe(true)
    expect(indicator.props('convergence')).toEqual(convergencePayload)
  })

  it('M3-T1 shows empty state when no agents returned', async () => {
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })

    const { wrapper } = mountSimulationView()

    await flushPromises()

    expect(wrapper.find('[data-test="simulation-agents-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="simulation-agent-state"]').exists()).toBe(false)
  })

  it('M3-T1 avoids fallback when store root_id is missing', async () => {
    const { wrapper } = mountSimulationView({
      rootId: '',
      branchId: 'branch-store',
      sceneId: '',
      routeQuery: {},
    })

    await loadAgentsManually(wrapper)

    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    expectMissingContextState(wrapper)
  })

  it('M3-T1 avoids fallback when store branch_id is missing', async () => {
    const { wrapper } = mountSimulationView({
      rootId: 'root-store',
      branchId: '',
      sceneId: '',
      routeQuery: {},
    })

    await loadAgentsManually(wrapper)

    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    expectMissingContextState(wrapper)
  })

  it('M3-T1 avoids fallback when store context is missing', async () => {
    const { wrapper } = mountSimulationView({
      rootId: '',
      branchId: '',
      sceneId: '',
      routeQuery: {},
    })

    await loadAgentsManually(wrapper)

    expect(simulationApiMock.fetchSimulationAgents).not.toHaveBeenCalled()
    expectMissingContextState(wrapper)
  })

  it('M3-T1 shows error state when agent load fails', async () => {
    simulationApiMock.fetchSimulationAgents.mockRejectedValue(new Error('network'))

    const { wrapper } = mountSimulationView()

    await flushPromises()

    expect(wrapper.find('[data-test="simulation-error"]').exists()).toBe(true)
  })

  it('M3-T1 uses real scene context when running a scene simulation', async () => {
    const realSceneId = 'scene-real-9'
    sceneApiMock.fetchSceneContext.mockResolvedValue({ data: { scene_id: realSceneId } })

    const { wrapper } = mountSimulationView({ sceneId: realSceneId })

    await flushPromises()

    const payload = await runSceneAndGetPayload(wrapper)

    expect(simulationApiMock.runScene).toHaveBeenCalled()
    expect(payload?.scene_context?.scene_id).toBe(realSceneId)
  })

  it('M3-T1 does not allow fake scene id format in runScene payload', async () => {
    const realSceneId = 'scene-real-12'
    sceneApiMock.fetchSceneContext.mockResolvedValue({ data: { scene_id: realSceneId } })

    const { wrapper } = mountSimulationView({ sceneId: realSceneId })

    await flushPromises()

    const payload = await runSceneAndGetPayload(wrapper)

    expect(simulationApiMock.runScene).toHaveBeenCalled()
    expect(payload?.scene_context?.scene_id).not.toMatch(/^scene-\d+$/)
  })

  it('M3-T1 falls back to route scene id when scene context misses scene_id', async () => {
    const realSceneId = 'scene-real-18'
    sceneApiMock.fetchSceneContext.mockResolvedValue({ data: {} })

    const { wrapper } = mountSimulationView({ sceneId: realSceneId })

    await flushPromises()

    const payload = await runSceneAndGetPayload(wrapper)

    expect(simulationApiMock.runScene).toHaveBeenCalled()
    expect(payload?.scene_context?.scene_id).toBe(realSceneId)
  })

  it('M3-T1 exposes invalid scene errors without leaking uncaught requests', async () => {
    sceneApiMock.fetchSceneContext.mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: 'scene not found',
        },
      },
    })

    const { wrapper } = mountSimulationView({ sceneId: 'scene-invalid-input' })

    await flushPromises()
    await wrapper.find('[data-test="simulation-scene"]').trigger('click')
    await flushPromises()

    expect(simulationApiMock.runScene).not.toHaveBeenCalled()
    const apiError = wrapper.find('[data-test="api-error"]')
    expect(apiError.exists()).toBe(true)
    expect(apiError.text()).toContain('scene not found')
  })

  it('M3-T1 blocks malformed scene id before network request', async () => {
    const malformedSceneId = '<script>alert(1)</script>'

    const { wrapper } = mountSimulationView({ sceneId: malformedSceneId })

    await flushPromises()
    await wrapper.find('[data-test="simulation-scene"]').trigger('click')
    await flushPromises()

    expect(sceneApiMock.fetchSceneContext).not.toHaveBeenCalled()
    expect(simulationApiMock.runScene).not.toHaveBeenCalled()
    const apiError = wrapper.find('[data-test="api-error"]')
    expect(apiError.exists()).toBe(true)
    expect(apiError.text()).toContain('scene_id format is invalid')
  })

  it('M3-T1 blocks unknown scene id before context request when scene list is loaded', async () => {
    sceneApiMock.fetchScenes.mockResolvedValue({
      scenes: [
        {
          id: 'scene-alpha',
        },
      ],
    })

    const { wrapper } = mountSimulationView({ sceneId: 'scene-not-in-project' })

    await flushPromises()

    expect(sceneApiMock.fetchSceneContext).not.toHaveBeenCalled()
    const apiError = wrapper.find('[data-test="api-error"]')
    expect(apiError.exists()).toBe(true)
    expect(apiError.text()).toContain('scene_id not found in current project')
  })
})

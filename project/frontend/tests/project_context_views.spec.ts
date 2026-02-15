import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useSnowflakeStore } from '@/stores/snowflake'
import SnowflakeView from '../src/views/SnowflakeView.vue'
import EditorView from '../src/views/EditorView.vue'
import SimulationView from '../src/views/SimulationView.vue'
import WorldView from '../src/views/WorldView.vue'
import * as branchApi from '@/api/branch'
import * as snowflakeApi from '@/api/snowflake'
import * as sceneApi from '@/api/scene'
import * as simulationApi from '@/api/simulation'
import * as entityApi from '@/api/entity'
import * as subplotApi from '@/api/subplot'
import * as anchorApi from '@/api/anchor'
import * as agentApi from '@/api/agent'

const routeState = vi.hoisted(() => ({
  params: { sceneId: 'scene-alpha' },
  query: { root_id: 'route-root', branch_id: 'route-branch' },
}))

const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: routerPushMock }),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
  renderScene: vi.fn(),
  updateScene: vi.fn(),
  diffScene: vi.fn(),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulations: vi.fn(),
  fetchSimulationAgents: vi.fn(),
  runRound: vi.fn(),
  runScene: vi.fn(),
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn(),
    switchBranch: vi.fn(),
    getBranchHistory: vi.fn(),
    getRootSnapshot: vi.fn(),
    resetBranch: vi.fn(),
  },
}))

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakePrompts: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: vi.fn(),
  fetchRelations: vi.fn(),
  createEntity: vi.fn(),
  updateEntity: vi.fn(),
  deleteEntity: vi.fn(),
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: vi.fn(),
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  fetchAgents: vi.fn(),
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

vi.mock('@/api/chapter', () => ({
  renderChapter: vi.fn(),
  reviewChapter: vi.fn(),
}))

const branchApiMock = vi.mocked(branchApi) as unknown as {
  branchApi: {
    listBranches: ReturnType<typeof vi.fn>
  }
}

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  snowflakeApi: {
    listActs: ReturnType<typeof vi.fn>
    listChapters: ReturnType<typeof vi.fn>
  }
}

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
}

const simulationApiMock = vi.mocked(simulationApi) as unknown as {
  fetchSimulationAgents: ReturnType<typeof vi.fn>
}

const entityApiMock = vi.mocked(entityApi) as unknown as {
  fetchEntities: ReturnType<typeof vi.fn>
}

const subplotApiMock = vi.mocked(subplotApi) as unknown as {
  fetchSubplots: ReturnType<typeof vi.fn>
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  fetchAnchors: ReturnType<typeof vi.fn>
}

const agentApiMock = vi.mocked(agentApi) as unknown as {
  fetchAgents: ReturnType<typeof vi.fn>
  agentApi: {
    getAgentState: ReturnType<typeof vi.fn>
  }
}

const setupPinia = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

const mountWithPinia = (component: unknown, pinia: ReturnType<typeof createPinia>, stubs = {}) =>
  mount(component as Record<string, unknown>, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
        ActionTimeline: true,
        AgentStatePanel: true,
        RoundPlayer: true,
        ...stubs,
      },
    },
  })

describe('project context view contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = 'scene-alpha'
    routeState.query = { root_id: 'route-root', branch_id: 'route-branch' }
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })
  })

  it('project context SnowflakeView uses project store ids', async () => {
    const pinia = setupPinia()
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('store-root', 'store-branch', '')

    const snowflakeStore = useSnowflakeStore()
    const restoreSpy = vi
      .spyOn(snowflakeStore, 'loadProgress')
      .mockResolvedValue({ step: 1 })

    mountWithPinia(SnowflakeView, pinia)
    await flushPromises()

    expect(restoreSpy).toHaveBeenCalledWith('store-root', 'store-branch')
  })

  it('project context SnowflakeView skips restore when store empty', async () => {
    const pinia = setupPinia()
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('', '', '')

    const snowflakeStore = useSnowflakeStore()
    const restoreSpy = vi
      .spyOn(snowflakeStore, 'loadProgress')
      .mockResolvedValue({ step: 1 })

    mountWithPinia(SnowflakeView, pinia)
    await flushPromises()

    expect(restoreSpy).not.toHaveBeenCalled()
  })

  it('project context EditorView uses store root for branches', async () => {
    const pinia = setupPinia()
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('store-root', 'store-branch', 'scene-alpha')

    branchApiMock.branchApi.listBranches.mockResolvedValue(['main'])
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])

    mountWithPinia(EditorView, pinia)
    await flushPromises()

    expect(branchApiMock.branchApi.listBranches).toHaveBeenCalledWith('store-root')
  })

  it('project context SimulationView uses store branch for scene context', async () => {
    const pinia = setupPinia()
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('store-root', 'store-branch', 'scene-alpha')

    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: 'scene-alpha' })

    mountWithPinia(SimulationView, pinia)
    await flushPromises()

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalledWith('scene-alpha', 'store-branch')
  })

  it('project context WorldView reacts to project switch', async () => {
    const pinia = setupPinia()
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('store-root', 'store-branch', '')

    entityApiMock.fetchEntities.mockResolvedValue([])
    anchorApiMock.fetchAnchors.mockResolvedValue([])
    subplotApiMock.fetchSubplots.mockResolvedValue([])

    const wrapper = mountWithPinia(WorldView, pinia)
    await flushPromises()

    projectStore.setCurrentProject('store-root-2', 'store-branch-2', '')

    const loadButton = wrapper.find('[data-test="world-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')
    await flushPromises()

    expect(entityApiMock.fetchEntities).toHaveBeenCalledWith('store-root-2', 'store-branch-2')
  })
})
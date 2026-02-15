import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import SimulationView from '../src/views/SimulationView.vue'
import { fetchScenes } from '@/api/scene'

const routeState = vi.hoisted(() => ({
  params: {},
  query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
}))

const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
  }),
}))

vi.mock('@/api/scene', () => ({
  fetchSceneContext: vi.fn(),
  fetchScenes: vi.fn(),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulationAgents: vi.fn(),
  fetchSimulations: vi.fn(),
  runRound: vi.fn(),
  runScene: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

const fetchScenesMock = vi.mocked(fetchScenes)

describe('M1-T2 simulation scene selection', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = { root_id: 'root-alpha', branch_id: 'branch-alpha' }
  })

  it('loads scenes and routes on selection', async () => {
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

    fetchScenesMock.mockResolvedValue({
      root_id: 'root-alpha',
      branch_id: 'branch-alpha',
      scenes: [
        { id: 'scene-alpha', branch_id: 'branch-alpha' },
        { id: 'scene-beta', branch_id: 'branch-alpha' },
      ],
    })

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

    expect(wrapper.exists()).toBe(true)
    await flushPromises()

    expect(fetchScenesMock).toHaveBeenCalledWith('root-alpha', 'branch-alpha')

    const select = wrapper.find('[data-test="simulation-scene-select"]')
    expect(select.exists()).toBe(true)
    await select.setValue('scene-beta')
    await flushPromises()

    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'simulation',
      params: { sceneId: 'scene-beta' },
      query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
    })
    expect(projectStore.scene_id).toBe('scene-beta')
  })
})

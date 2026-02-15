import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import SimulationView from '../views/SimulationView.vue'
import { useProjectStore } from '../stores/project'
import { useSimulationStore } from '../stores/simulation'
import { fetchSceneContext, fetchScenes } from '@/api/scene'
import { fetchSimulationAgents } from '@/api/simulation'
import { agentApi } from '@/api/agent'

const routeState = reactive({
  name: 'simulation',
  params: { sceneId: 'scene-alpha' },
  query: {},
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulationAgents: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('SimulationView runRound data loading', () => {
  beforeEach(() => {
  vi.clearAllMocks()
})

  it('loads scene context and agents before running a round', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const projectStore = useProjectStore()
    projectStore.setProject('root-alpha', 'main', 'scene-alpha')

    const simulationStore = useSimulationStore()
    const runRoundSpy = vi
      .spyOn(simulationStore, 'runRound')
      .mockResolvedValue({ round_id: 'round-alpha', convergence_score: 0 })

    vi.mocked(fetchSceneContext).mockResolvedValue({
      data: { scene_id: 'scene-alpha', title: 'Scene Alpha' },
    })
    vi.mocked(fetchSimulationAgents).mockResolvedValue({
      agents: [
        {
          id: 'agent-alpha',
          character_id: 'character-alpha',
          beliefs: { focus: 'goal' },
          desires: [],
          intentions: [],
          memory: [],
          private_knowledge: {},
        },
      ],
    })

    vi.mocked(fetchScenes).mockResolvedValue({ scenes: [] })

    vi.mocked(agentApi.getAgentState).mockResolvedValue({
      id: 'agent-alpha',
      character_id: 'character-alpha',
      branch_id: 'main',
      beliefs: { focus: 'goal' },
      desires: [],
      intentions: [],
      memory: [],
      private_knowledge: {},
      last_updated_scene: 1,
      version: 1,
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

    await flushPromises()
    await nextTick()

    vi.mocked(fetchSceneContext).mockClear()
    vi.mocked(fetchSimulationAgents).mockClear()
    runRoundSpy.mockClear()

    await wrapper.get('[data-test="simulation-step"]').trigger('click')
    await flushPromises()

    expect(fetchSceneContext).toHaveBeenCalledWith('scene-alpha', 'main')
    expect(fetchSimulationAgents).toHaveBeenCalledWith('root-alpha', 'main')
    expect(runRoundSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        scene_context: expect.objectContaining({ scene_id: 'scene-alpha' }),
        agents: [
          expect.objectContaining({
            id: 'agent-alpha',
            character_id: 'character-alpha',
            branch_id: 'main',
          }),
        ],
      }),
    )
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import SimulationView from '../views/SimulationView.vue'
import { useProjectStore } from '../stores/project'
import { useSimulationStore } from '../stores/simulation'
import { useSnowflakeStore } from '../stores/snowflake'
import { createProject, fetchProject, fetchProjects } from '@/api/project'
import { fetchSceneContext, fetchScenes } from '@/api/scene'
import { fetchSimulationAgents } from '@/api/simulation'

const routeState = reactive({
  name: 'simulation',
  params: { sceneId: 'scene-alpha' },
  query: {},
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('@/api/project', () => ({
  fetchProjects: vi.fn(),
  fetchProject: vi.fn(),
  createProject: vi.fn(),
  deleteProject: vi.fn(),
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn(),
    createBranch: vi.fn(),
    switchBranch: vi.fn(),
  },
}))

vi.mock('../api/branch', () => ({
  branchApi: {
    getRootSnapshot: vi.fn(),
  },
}))

vi.mock('../api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
}))

vi.mock('../api/anchor', () => ({
  anchorApi: {
    listAnchors: vi.fn(),
    generateAnchors: vi.fn(),
  },
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

describe('Iteration 10 edge cases', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    vi.mocked(fetchScenes).mockResolvedValue({ scenes: [] })
  })

  describe('empty value tests', () => {
    it('project.loadBranches rejects empty root_id', async () => {
      const store = useProjectStore()
      await expect(store.loadBranches('')).rejects.toThrow('root_id is required')
    })

    it('project.createBranch rejects missing identifiers', async () => {
      const store = useProjectStore()
      await expect(store.createBranch('', 'feature-alpha')).rejects.toThrow(
        'root_id and branch_id are required',
      )
      await expect(store.createBranch('root-alpha', '')).rejects.toThrow(
        'root_id and branch_id are required',
      )
    })

    it('project.switchBranch rejects missing identifiers', async () => {
      const store = useProjectStore()
      await expect(store.switchBranch('root-alpha', '')).rejects.toThrow(
        'root_id and branch_id are required',
      )
      await expect(store.switchBranch('', 'main')).rejects.toThrow('root_id and branch_id are required')
    })

    it('project.deleteProject rejects empty root_id', async () => {
      const store = useProjectStore()
      await expect(store.deleteProject('')).rejects.toThrow('root_id is required')
    })

    it('project.loadProject rejects empty root_id', async () => {
      const store = useProjectStore()
      await expect(store.loadProject('')).rejects.toThrow('root_id is required')
    })

    it('project.saveProject rejects empty name', async () => {
      const store = useProjectStore()
      await expect(store.saveProject({ name: '' })).rejects.toThrow('Project name is required')
    })

    it('snowflake.saveStepToBackend rejects when root id missing', async () => {
      const store = useSnowflakeStore()
      await expect(store.saveStepToBackend('step1', {})).rejects.toThrow(
        'root_id is required for saving snowflake step',
      )
    })

    it('snowflake.restoreFromBackend rejects empty root_id', async () => {
      const store = useSnowflakeStore()
      await expect(store.restoreFromBackend('')).rejects.toThrow(
        'root_id is required for restoring snowflake state',
      )
    })
  })

  describe('boundary value tests', () => {
    it('project.saveProject accepts name length 255', async () => {
      const store = useProjectStore()
      const name = 'a'.repeat(255)
      vi.mocked(createProject).mockResolvedValue({
        root_id: 'root-max',
        name,
        created_at: 'now',
        updated_at: 'later',
      })

      const created = await store.saveProject({ name })
      expect(createProject).toHaveBeenCalledWith(name)
      expect(created.root_id).toBe('root-max')
      expect(store.projects.length).toBe(1)
    })

    it('project.saveProject rejects name length 256', async () => {
      const store = useProjectStore()
      await expect(store.saveProject({ name: 'a'.repeat(256) })).rejects.toThrow('Project name is too long')
    })

    it('project.listProjects handles empty project list', async () => {
      const store = useProjectStore()
      vi.mocked(fetchProjects).mockResolvedValue({ roots: [] })
      await store.listProjects()
      expect(store.projects).toEqual([])
    })

    it('project.listProjects marks timeout and rethrows', async () => {
      const store = useProjectStore()
      vi.mocked(fetchProjects).mockRejectedValue(new Error('timeout'))
      await expect(store.listProjects()).rejects.toThrow('timeout')
      expect(store.project_list_error).toBe('timeout')
      expect(store.project_list_timeout).toBe(true)
    })
  })

  describe('type boundary tests', () => {
    it('project.loadProject rejects non-object payload', async () => {
      const store = useProjectStore()
      vi.mocked(fetchProject).mockResolvedValue(null)
      await expect(store.loadProject('root-alpha')).rejects.toThrow('project payload is required')
    })

    it('project.loadProject normalizes missing fields', async () => {
      const store = useProjectStore()
      vi.mocked(fetchProject).mockResolvedValue({
        data: {
          root_id: '',
          branch_id: '   ',
          scene_id: 123,
        },
      })

      await store.loadProject('root-alpha')

      expect(store.root_id).toBe('root-alpha')
      expect(store.branch_id).toBe('main')
      expect(store.scene_id).toBe('')
    })

    it('SimulationView accepts JSON string scene context and empty agents list', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const projectStore = useProjectStore()
      projectStore.setProject('root-alpha', 'main', 'scene-alpha')

      const simulationStore = useSimulationStore()
      const runRoundSpy = vi
        .spyOn(simulationStore, 'runRound')
        .mockResolvedValue({ round_id: 'round-1', convergence_score: 0 })

      vi.mocked(fetchSceneContext).mockResolvedValue(
        JSON.stringify({ data: { scene_id: 'scene-alpha', title: 'Scene Alpha' } }),
      )
      vi.mocked(fetchSimulationAgents).mockResolvedValue({ agents: [] })

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
          agents: [],
        }),
      )
    })
  })

  describe('concurrency / timing tests', () => {
    it('SimulationView Step called twice triggers two rounds', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const projectStore = useProjectStore()
      projectStore.setProject('root-alpha', 'main', 'scene-alpha')

      const simulationStore = useSimulationStore()
      const runRoundSpy = vi
        .spyOn(simulationStore, 'runRound')
        .mockResolvedValueOnce({ round_id: 'round-1', convergence_score: 0 })
        .mockResolvedValueOnce({ round_id: 'round-2', convergence_score: 0 })

      vi.mocked(fetchSceneContext).mockResolvedValue({ data: { scene_id: 'scene-alpha' } })
      vi.mocked(fetchSimulationAgents).mockResolvedValue({ agents: [] })

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
      await wrapper.get('[data-test="simulation-step"]').trigger('click')
      await flushPromises()

      expect(runRoundSpy).toHaveBeenCalledTimes(2)
      expect(runRoundSpy.mock.calls[0]?.[0]).toEqual(
        expect.objectContaining({ round_id: 'round-1' }),
      )
      expect(runRoundSpy.mock.calls[1]?.[0]).toEqual(
        expect.objectContaining({ round_id: 'round-2' }),
      )
    })
  })
})

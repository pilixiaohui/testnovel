import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type {
  SnowflakeAct,
  SnowflakeAnchor,
  SnowflakeChapter,
  SnowflakeCharacter,
  SnowflakeSceneNode,
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakeStep5Payload,
  SnowflakeStructure,
} from '@/types/snowflake'
import type { WorldEntity } from '@/types/entity'
import { useSnowflakeStore } from '@/stores/snowflake'
import { useSimulationStore } from '@/stores/simulation'
import { useProjectStore } from '@/stores/project'
import { useWorldStore } from '@/stores/world'
import * as snowflakeApi from '@/api/snowflake'
import * as anchorApi from '@/api/anchor'
import * as simulationApi from '@/api/simulation'
import * as sceneApi from '@/api/scene'
import * as commitApi from '@/api/commit'
import * as entityApi from '@/api/entity'
import * as subplotApi from '@/api/subplot'
import SnowflakeFlow from '../src/views/SnowflakeView.vue'
import SimulationConsole from '../src/views/SimulationView.vue'
import SceneEditor from '../src/views/EditorView.vue'
import WorldManager from '../src/views/WorldView.vue'

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn().mockResolvedValue([]),
    listChapters: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
  anchorApi: {
    generateAnchors: vi.fn(),
    listAnchors: vi.fn(),
    updateAnchor: vi.fn(),
    checkAnchor: vi.fn(),
  },
}))

vi.mock('@/api/simulation', () => ({
  fetchSimulations: vi.fn(),
  fetchSimulationAgents: vi.fn(),
  runRound: vi.fn(),
  runScene: vi.fn(),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn().mockResolvedValue({ data: { scene_id: 'scene-alpha' } }),
  renderScene: vi.fn(),
  updateScene: vi.fn(),
  diffScene: vi.fn(),
}))

vi.mock('@/api/commit', () => ({
  commitApi: {
    commitScene: vi.fn(),
  },
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: vi.fn(),
  createEntity: vi.fn(),
  updateEntity: vi.fn(),
  deleteEntity: vi.fn(),
  fetchRelations: vi.fn(),
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: vi.fn(),
}))

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

vi.mock('@/api/agent', () => ({
  fetchAgents: vi.fn().mockResolvedValue([]),
  agentApi: {
    getAgentState: vi.fn(),
  },
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn().mockResolvedValue(['main']),
    switchBranch: vi.fn(),
    getBranchHistory: vi.fn(),
    getRootSnapshot: vi.fn(),
    resetBranch: vi.fn(),
  },
}))

const snowflakeApiMock = vi.mocked(snowflakeApi)
const anchorApiMock = vi.mocked(anchorApi)
const simulationApiMock = vi.mocked(simulationApi) as unknown as {
  fetchSimulations: ReturnType<typeof vi.fn>
  fetchSimulationAgents: ReturnType<typeof vi.fn>
  runRound: ReturnType<typeof vi.fn>
  runScene: ReturnType<typeof vi.fn>
}
const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
  renderScene: ReturnType<typeof vi.fn>
  updateScene: ReturnType<typeof vi.fn>
  diffScene: ReturnType<typeof vi.fn>
}
const commitApiMock = vi.mocked(commitApi) as unknown as {
  commitApi: {
    commitScene: ReturnType<typeof vi.fn>
  }
}
const entityApiMock = vi.mocked(entityApi) as unknown as {
  fetchEntities: ReturnType<typeof vi.fn>
  createEntity: ReturnType<typeof vi.fn>
  updateEntity: ReturnType<typeof vi.fn>
  deleteEntity: ReturnType<typeof vi.fn>
  fetchRelations: ReturnType<typeof vi.fn>
}
const subplotApiMock = vi.mocked(subplotApi) as unknown as {
  fetchSubplots: ReturnType<typeof vi.fn>
}

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0))

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

const setupSimulationConsole = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore(pinia)
  projectStore.setProject('root-alpha', 'branch-alpha', 'scene-alpha')
  sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
  simulationApiMock.fetchSimulationAgents.mockResolvedValue({ agents: [] })
  const wrapper = mount(SimulationConsole, { global: { plugins: [pinia] } })
  const store = useSimulationStore(pinia)
  return { wrapper, store }
}

const setupSceneEditor = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
  const wrapper = mount(SceneEditor, { global: { plugins: [pinia] } })
  return { wrapper }
}

const setupWorldManager = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(WorldManager, { global: { plugins: [pinia] } })
  const store = useWorldStore()
  return { wrapper, store }
}

describe('M1-T2 core views contract', () => {
  it('SnowflakeFlow exposes root, list, and primary action', () => {
    const wrapper = mountView(SnowflakeFlow)
    expect(wrapper.find('[data-test="snowflake-flow-root"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="snowflake-step-list"]').exists()).toBe(true)
    const addButton = wrapper.find('[data-test="snowflake-add-step"]')
    expect(addButton.exists()).toBe(true)
    expect(addButton.element.tagName).toBe('BUTTON')
  })

  it('SimulationConsole exposes console root, log, and controls', () => {
    const wrapper = mountView(SimulationConsole)
    expect(wrapper.find('[data-test="simulation-console-root"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="simulation-log"]').exists()).toBe(true)
    const startButton = wrapper.find('[data-test="simulation-start"]')
    expect(startButton.exists()).toBe(true)
    expect(startButton.element.tagName).toBe('BUTTON')
  })

  it('SceneEditor exposes editor root, form, and save action', () => {
    const wrapper = mountView(SceneEditor)
    expect(wrapper.find('[data-test="scene-editor-root"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="scene-editor-form"]').exists()).toBe(true)
    const saveButton = wrapper.find('[data-test="scene-save"]')
    expect(saveButton.exists()).toBe(true)
    expect(saveButton.element.tagName).toBe('BUTTON')
  })

  it('WorldManager exposes root, list, and create action', () => {
    const wrapper = mountView(WorldManager)
    expect(wrapper.find('[data-test="world-manager-root"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="world-list"]').exists()).toBe(true)
    const createButton = wrapper.find('[data-test="world-create"]')
    expect(createButton.exists()).toBe(true)
    expect(createButton.element.tagName).toBe('BUTTON')
  })
})

describe('M1-T2 snowflake integration flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('runs step1-6 end-to-end and updates state', async () => {
    const store = useSnowflakeStore()
    expect(store.steps.logline).toEqual([])

    const loglines = ['one-sentence idea']
    const root: SnowflakeStructure = {
      logline: 'root-logline',
      three_disasters: ['d1', 'd2', 'd3'],
      ending: 'ending',
      theme: 'theme',
    }
    const characters: SnowflakeCharacter[] = [
      {
        entity_id: 'c1',
        name: 'Hero',
        ambition: 'goal',
        conflict: 'conflict',
        epiphany: 'epiphany',
        voice_dna: 'voice',
      },
    ]
    const scenes: SnowflakeSceneNode[] = [
      {
        id: 's1',
        branch_id: 'b1',
        parent_act_id: null,
        pov_character_id: 'c1',
        expected_outcome: 'win',
        conflict_type: 'internal',
        actual_outcome: 'lose',
        logic_exception: false,
        is_dirty: false,
      },
    ]
    const step4Result: SnowflakeStep4Result = {
      root_id: 'root-alpha',
      branch_id: 'branch-alpha',
      scenes,
    }
    const acts: SnowflakeAct[] = [{ id: 'act-1' }]
    const chapters: SnowflakeChapter[] = [{ id: 'chapter-1' }]
    const anchors: SnowflakeAnchor[] = [{ id: 'anchor-1' }]

    snowflakeApiMock.fetchSnowflakeStep1.mockResolvedValue(loglines)
    snowflakeApiMock.fetchSnowflakeStep2.mockResolvedValue(root)
    snowflakeApiMock.fetchSnowflakeStep3.mockResolvedValue(characters)
    snowflakeApiMock.fetchSnowflakeStep4.mockResolvedValue(step4Result)
    snowflakeApiMock.fetchSnowflakeStep5.mockResolvedValue(acts)
    snowflakeApiMock.fetchSnowflakeStep6.mockResolvedValue(chapters)
    anchorApiMock.anchorApi.generateAnchors.mockResolvedValue(anchors)

    await store.fetchStep1('idea')
    expect(snowflakeApiMock.fetchSnowflakeStep1).toHaveBeenCalledWith('idea')
    expect(store.logline).toEqual(loglines)

    await store.fetchStep2(loglines[0])
    expect(snowflakeApiMock.fetchSnowflakeStep2).toHaveBeenCalledWith(loglines[0])
    expect(store.root).toEqual(root)

    await store.fetchStep3(root)
    expect(snowflakeApiMock.fetchSnowflakeStep3).toHaveBeenCalledWith(root)
    expect(store.characters).toEqual(characters)

    const step4Payload: SnowflakeStep4Payload = {
      root,
      characters,
    }
    await store.fetchStep4(step4Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep4).toHaveBeenCalledWith(step4Payload)
    expect(store.scenes).toEqual(scenes)

    const step5Payload: SnowflakeStep5Payload = {
      root_id: step4Result.root_id,
      root,
      characters,
    }
    await store.fetchStep5(step5Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep5).toHaveBeenCalledWith(step5Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep6).toHaveBeenCalledWith(step5Payload)
    expect(store.acts).toEqual(acts)
    expect(store.chapters).toEqual(chapters)

    await store.fetchStep6()
    expect(anchorApiMock.anchorApi.generateAnchors).toHaveBeenCalled()
    expect(store.anchors).toEqual(anchors)
  })

  it('does not advance when a step API fails', async () => {
    const store = useSnowflakeStore()

    const loglines = ['one-sentence idea']
    const root: SnowflakeStructure = {
      logline: 'root-logline',
      three_disasters: ['d1', 'd2', 'd3'],
      ending: 'ending',
      theme: 'theme',
    }

    snowflakeApiMock.fetchSnowflakeStep1.mockResolvedValue(loglines)
    snowflakeApiMock.fetchSnowflakeStep2.mockResolvedValue(root)
    snowflakeApiMock.fetchSnowflakeStep3.mockRejectedValue(new Error('step3 failed'))

    await store.fetchStep1('idea')
    await store.fetchStep2(loglines[0])

    await expect(store.fetchStep3(root)).rejects.toThrow('step3 failed')

    expect(store.characters).toEqual([])
    expect(store.scenes).toEqual([])
    expect(store.acts).toEqual([])
    expect(store.chapters).toEqual([])
    expect(store.anchors).toEqual([])
  })
})

describe('M2-T1 simulation console integration flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads simulations via UI and updates state/log panel', async () => {
    const { wrapper, store } = setupSimulationConsole()

    const simulationConfigs = [
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
        convergence_score: 0.12,
        drama_score: 0.2,
        info_gain: 0.1,
        stagnation_count: 0,
      },
    ]

    simulationApiMock.fetchSimulations.mockResolvedValue(simulationConfigs)

    const startButton = wrapper.find('[data-test="simulation-start"]')
    expect(startButton.exists()).toBe(true)
    await startButton.trigger('click')

    expect(simulationApiMock.fetchSimulations).toHaveBeenCalled()
    expect(store.status).toBe('running')

    const logItems = wrapper.findAll('.log-line')
    expect(logItems.length).toBe(simulationConfigs.length)
  })

  it('runs round/scene via UI and shows convergence indicator', async () => {
    const { wrapper, store } = setupSimulationConsole()

    const runRoundSpy = vi.spyOn(store, 'runRound').mockImplementation(async () => {
      store.setStatus('running')
      return { convergence: true }
    })

    const stepButton = wrapper.find('[data-test="simulation-step"]')
    expect(stepButton.exists()).toBe(true)
    await stepButton.trigger('click')
    await flushPromises()

    expect(runRoundSpy).toHaveBeenCalled()
    expect(store.status).toBe('running')

    const converged = wrapper.find('[data-test="simulation-converged"]')
    expect(converged.exists()).toBe(true)
  })

  it('does not advance when load API fails', async () => {
    const { wrapper, store } = setupSimulationConsole()

    simulationApiMock.fetchSimulations.mockRejectedValue(new Error('load failed'))

    const startButton = wrapper.find('[data-test="simulation-start"]')
    expect(startButton.exists()).toBe(true)
    await startButton.trigger('click')

    expect(simulationApiMock.fetchSimulations).toHaveBeenCalled()
    expect(store.status).toBe('idle')
  })
})

describe('M2-T2 scene editor integration flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    commitApiMock.commitApi.commitScene.mockResolvedValue({
      commit_id: 'commit-alpha',
      scene_version_ids: [],
    })
  })

  it('loads scene context/render via UI', async () => {
    const { wrapper } = setupSceneEditor()

    sceneApiMock.fetchSceneContext.mockResolvedValue({ id: 'scene-alpha', summary: 'Loaded' })
    sceneApiMock.renderScene.mockResolvedValue({ content: 'Rendered' })

    const loadButton = wrapper.find('[data-test="scene-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalled()
    expect(sceneApiMock.renderScene).toHaveBeenCalled()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    expect(summaryInput.exists()).toBe(true)
  })

  it('edits summary/outcome and saves via update API', async () => {
    const { wrapper } = setupSceneEditor()

    sceneApiMock.updateScene.mockResolvedValue({ id: 'scene-alpha', summary: 'Updated' })

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    expect(summaryInput.exists()).toBe(true)
    await summaryInput.setValue('Updated summary')

    const outcomeSelect = wrapper.find('[data-test="scene-outcome-select"]')
    expect(outcomeSelect.exists()).toBe(true)
    await outcomeSelect.trigger('change')

    const saveButton = wrapper.find('[data-test="scene-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')

    expect(sceneApiMock.updateScene).toHaveBeenCalled()
  })

  it('updates diff/render and dirty flag', async () => {
    const { wrapper } = setupSceneEditor()

    sceneApiMock.diffScene.mockResolvedValue({ diff: 'diff' })
    sceneApiMock.renderScene.mockResolvedValue({ content: 'rendered' })

    const diffButton = wrapper.find('[data-test="scene-diff"]')
    expect(diffButton.exists()).toBe(true)
    await diffButton.trigger('click')

    expect(sceneApiMock.diffScene).toHaveBeenCalled()

    const renderButton = wrapper.find('[data-test="scene-render"]')
    expect(renderButton.exists()).toBe(true)
    await renderButton.trigger('click')

    expect(sceneApiMock.renderScene).toHaveBeenCalled()

    const dirtyFlag = wrapper.find('[data-test="scene-dirty"]')
    expect(dirtyFlag.exists()).toBe(true)
  })

  it('does not advance when load API fails', async () => {
    const { wrapper } = setupSceneEditor()

    sceneApiMock.fetchSceneContext.mockRejectedValue(new Error('load failed'))

    const loadButton = wrapper.find('[data-test="scene-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalled()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    expect(summaryInput.exists()).toBe(true)
  })
})

describe('M2-T3 world manager integration flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads entities/anchors/subplots via UI and updates lists', async () => {
    const { wrapper, store } = setupWorldManager()

    const entities: WorldEntity[] = [
      {
        id: 'e1',
        created_at: '2024-01-01',
        name: 'Entity 1',
        type: 'character',
        position: { x: 0, y: 0, z: 0 },
      },
    ]
    const anchors = ['Anchor 1']
    const subplots = ['Subplot 1']

    entityApiMock.fetchEntities.mockResolvedValue(entities)
    anchorApiMock.fetchAnchors.mockResolvedValue(anchors)
    subplotApiMock.fetchSubplots.mockResolvedValue(subplots)

    const loadButton = wrapper.find('[data-test="world-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')

    expect(entityApiMock.fetchEntities).toHaveBeenCalled()
    expect(anchorApiMock.fetchAnchors).toHaveBeenCalled()
    expect(subplotApiMock.fetchSubplots).toHaveBeenCalled()

    expect(store.entities).toEqual(entities)
    expect(store.anchors).toEqual(anchors)
  })

  it('creates, updates, and deletes entities via UI', async () => {
    const { wrapper } = setupWorldManager()

    entityApiMock.createEntity.mockResolvedValue({ id: 'e2' })
    entityApiMock.updateEntity.mockResolvedValue({ id: 'e2' })
    entityApiMock.deleteEntity.mockResolvedValue({ id: 'e2' })

    const createButton = wrapper.find('[data-test="world-entity-create"]')
    expect(createButton.exists()).toBe(true)
    await createButton.trigger('click')
    expect(entityApiMock.createEntity).toHaveBeenCalled()

    const updateButton = wrapper.find('[data-test="world-entity-update"]')
    expect(updateButton.exists()).toBe(true)
    await updateButton.trigger('click')
    expect(entityApiMock.updateEntity).toHaveBeenCalled()

    const deleteButton = wrapper.find('[data-test="world-entity-delete"]')
    expect(deleteButton.exists()).toBe(true)
    await deleteButton.trigger('click')
    expect(entityApiMock.deleteEntity).toHaveBeenCalled()
  })

  it('renders relations graph data via UI', async () => {
    const { wrapper } = setupWorldManager()

    entityApiMock.fetchRelations.mockResolvedValue([{ source: 'e1', target: 'e2' }])

    const graphButton = wrapper.find('[data-test="world-relations-show"]')
    expect(graphButton.exists()).toBe(true)
    await graphButton.trigger('click')

    expect(entityApiMock.fetchRelations).toHaveBeenCalled()

    const graph = wrapper.find('[data-test="world-relations-graph"]')
    expect(graph.exists()).toBe(true)
  })

  it('does not advance when load API fails', async () => {
    const { wrapper, store } = setupWorldManager()

    entityApiMock.fetchEntities.mockRejectedValue(new Error('load failed'))

    const loadButton = wrapper.find('[data-test="world-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')

    expect(entityApiMock.fetchEntities).toHaveBeenCalled()

    expect(store.entities).toEqual([])
    expect(store.anchors).toEqual([])
  })
})

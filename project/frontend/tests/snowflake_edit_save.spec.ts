import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useSnowflakeStore } from '@/stores/snowflake'
import SnowflakeView from '../src/views/SnowflakeView.vue'
import * as snowflakeApi from '@/api/snowflake'

const routeState = vi.hoisted(() => ({
  params: {},
  query: {},
}))

const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
  }),
}))

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  fetchSnowflakePrompts: vi.fn(),
  saveSnowflakePrompts: vi.fn(),
  resetSnowflakePrompts: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
  updateSnowflakeLogline: vi.fn(),
  updateSnowflakeCharacter: vi.fn(),
  updateSnowflakeAct: vi.fn(),
  updateSnowflakeChapter: vi.fn(),
  updateSnowflakeScene: vi.fn(),
}))

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  saveSnowflakeStep: ReturnType<typeof vi.fn>
}

const seedSnowflakeStore = () => {
  const store = useSnowflakeStore()
  store.id = 'root-alpha'
  store.steps.logline = ['Original logline']
  store.steps.root = {
    logline: 'Original logline',
    theme: 'theme',
    ending: 'ending',
    three_disasters: ['d1', 'd2', 'd3'],
  }
  store.steps.characters = [
    {
      entity_id: 'char-1',
      name: 'Hero',
      ambition: 'goal',
      conflict: 'conflict',
      epiphany: 'epiphany',
      voice_dna: 'voice',
    } as unknown as (typeof store.steps.characters)[number],
  ]
  store.steps.scenes = [
    {
      id: 'scene-alpha',
      title: 'Opening',
      sequence_index: 1,
      parent_act_id: 'act-1',
      expected_outcome: 'arrive',
      conflict_type: 'inner',
      pov_character_id: 'char-1',
      actual_outcome: '',
      branch_id: 'branch-alpha',
      is_dirty: false,
    } as unknown as (typeof store.steps.scenes)[number],
  ]
  store.steps.acts = [
    {
      id: 'act-1',
      root_id: 'root-alpha',
      sequence: 1,
      title: 'Act One',
      purpose: 'setup',
      tone: 'calm',
    },
  ]
  store.steps.chapters = [
    {
      id: 'chapter-1',
      act_id: 'act-1',
      sequence: 1,
      title: 'Chapter One',
      focus: 'intro',
    },
  ]
  store.steps.anchors = [
    {
      id: 'anchor-1',
      anchor_type: 'inciting_incident',
      description: 'seed anchor',
      constraint_type: 'hard',
      required_conditions: ['condition-a'],
    } as unknown as (typeof store.steps.anchors)[number],
  ]
  return store
}

const setupSnowflake = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')
  const store = seedSnowflakeStore()
  vi.spyOn(store, 'loadProgress').mockResolvedValue({ step: 4 })
  const wrapper = mount(SnowflakeView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
    },
  })
  return { wrapper }
}

describe('M2-T2 snowflake edit/save', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = {}
    snowflakeApiMock.saveSnowflakeStep.mockResolvedValue({ ok: true })
  })

  it('edits snowflake results and persists all steps through saveSnowflakeStep', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const loglineInputs = wrapper.findAll('[data-test="snowflake-logline-input"]')
    expect(loglineInputs.length).toBeGreaterThan(0)
    await loglineInputs[0].setValue('Updated logline')

    const characterNameInputs = wrapper.findAll('[data-test="snowflake-character-name-input"]')
    expect(characterNameInputs.length).toBeGreaterThan(0)
    await characterNameInputs[0].setValue('Updated Hero')

    const actTitleInputs = wrapper.findAll('[data-test="snowflake-act-title-input"]')
    expect(actTitleInputs.length).toBeGreaterThan(0)
    await actTitleInputs[0].setValue('Updated Act')

    const chapterTitleInputs = wrapper.findAll('[data-test="snowflake-chapter-title-input"]')
    expect(chapterTitleInputs.length).toBeGreaterThan(0)
    await chapterTitleInputs[0].setValue('Updated Chapter')

    const sceneTitleInputs = wrapper.findAll('[data-test="snowflake-scene-title-input"]')
    expect(sceneTitleInputs.length).toBeGreaterThan(0)
    await sceneTitleInputs[0].setValue('Updated Scene')

    await flushPromises()
    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)

    const saveButton = wrapper.find('[data-test="save-project-btn"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step1',
      data: { logline: ['Updated logline'] },
    })
    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step3',
      data: {
        characters: [expect.objectContaining({ id: 'char-1', name: 'Updated Hero' })],
      },
    })
    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step4',
      data: {
        scenes: [expect.objectContaining({ id: 'scene-alpha', title: 'Updated Scene' })],
      },
    })
    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step5',
      data: {
        acts: [expect.objectContaining({ id: 'act-1', title: 'Updated Act' })],
        chapters: [expect.objectContaining({ id: 'chapter-1', title: 'Updated Chapter' })],
      },
    })
    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step6',
      data: {
        anchors: [expect.objectContaining({ id: 'anchor-1' })],
      },
    })
    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(false)
  })

  it('blocks save when scene title is missing', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const sceneTitleInputs = wrapper.findAll('[data-test="snowflake-scene-title-input"]')
    expect(sceneTitleInputs.length).toBeGreaterThan(0)
    await sceneTitleInputs[0].setValue('')
    await flushPromises()

    const saveButton = wrapper.find('[data-test="save-project-btn"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakeStep).not.toHaveBeenCalled()
    const errorPanel = wrapper.find('[data-test="snowflake-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('scene.title')
  })

  it('keeps dirty state and shows error when save fails', async () => {
    snowflakeApiMock.saveSnowflakeStep.mockRejectedValue(new Error('save failed'))

    const { wrapper } = setupSnowflake()
    await flushPromises()

    const loglineInputs = wrapper.findAll('[data-test="snowflake-logline-input"]')
    expect(loglineInputs.length).toBeGreaterThan(0)
    await loglineInputs[0].setValue('Dirty logline')
    await flushPromises()

    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)

    const saveButton = wrapper.find('[data-test="save-project-btn"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalled()
    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)
    const errorPanel = wrapper.find('[data-test="snowflake-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text().length).toBeGreaterThan(0)
  })
})

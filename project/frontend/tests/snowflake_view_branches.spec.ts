import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useSnowflakeStore } from '@/stores/snowflake'
import SnowflakeView from '../src/views/SnowflakeView.vue'
import * as snowflakeApi from '@/api/snowflake'
import * as anchorApi from '@/api/anchor'

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

vi.mock('@/api/anchor', () => ({
  anchorApi: {
    generateAnchors: vi.fn(),
    listAnchors: vi.fn(),
  },
}))

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  fetchSnowflakeStep2: ReturnType<typeof vi.fn>
  fetchSnowflakeStep3: ReturnType<typeof vi.fn>
  fetchSnowflakeStep4: ReturnType<typeof vi.fn>
  fetchSnowflakeStep5: ReturnType<typeof vi.fn>
  fetchSnowflakeStep6: ReturnType<typeof vi.fn>
  fetchSnowflakePrompts: ReturnType<typeof vi.fn>
  saveSnowflakePrompts: ReturnType<typeof vi.fn>
  resetSnowflakePrompts: ReturnType<typeof vi.fn>
  saveSnowflakeStep: ReturnType<typeof vi.fn>
  updateSnowflakeLogline: ReturnType<typeof vi.fn>
  updateSnowflakeCharacter: ReturnType<typeof vi.fn>
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  anchorApi: {
    generateAnchors: ReturnType<typeof vi.fn>
    listAnchors: ReturnType<typeof vi.fn>
  }
}

const makeRoot = () => ({
  logline: 'root',
  theme: 'theme',
  ending: 'ending',
  three_disasters: ['disaster-1', 'disaster-2', 'disaster-3'],
})

const setupSnowflake = (setupStore?: (projectStore: ReturnType<typeof useProjectStore>, store: ReturnType<typeof useSnowflakeStore>) => void) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  const store = useSnowflakeStore()
  setupStore?.(projectStore, store)
  vi.spyOn(store, 'loadProgress').mockResolvedValue({ step: 1 })

  const wrapper = mount(SnowflakeView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
    },
  })

  return { wrapper, projectStore, store }
}

describe('SnowflakeView branch coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params = {}
    routeState.query = {}
    snowflakeApiMock.fetchSnowflakePrompts.mockResolvedValue({
      step1: 'p1',
      step2: 'p2',
      step3: 'p3',
      step4: 'p4',
      step5: 'p5',
      step6: 'p6',
    })
    snowflakeApiMock.fetchSnowflakeStep2.mockResolvedValue(makeRoot())
    snowflakeApiMock.fetchSnowflakeStep3.mockResolvedValue([])
    snowflakeApiMock.saveSnowflakePrompts.mockResolvedValue({ ok: true })
    snowflakeApiMock.resetSnowflakePrompts.mockResolvedValue({
      step1: 'p1',
      step2: 'p2',
      step3: 'p3',
      step4: 'p4',
      step5: 'p5',
      step6: 'p6',
    })
    snowflakeApiMock.fetchSnowflakeStep4.mockResolvedValue({
      root_id: 'root-9',
      branch_id: 'branch-9',
      scenes: [],
    })
    snowflakeApiMock.fetchSnowflakeStep5.mockResolvedValue([])
    snowflakeApiMock.fetchSnowflakeStep6.mockResolvedValue([])
    snowflakeApiMock.saveSnowflakeStep.mockResolvedValue({ ok: true })
    snowflakeApiMock.updateSnowflakeLogline.mockResolvedValue({ ok: true })
    snowflakeApiMock.updateSnowflakeCharacter.mockResolvedValue({ ok: true })
    anchorApiMock.anchorApi.generateAnchors.mockResolvedValue([])
  })

  it('skips loading when project root is missing', async () => {
    const { wrapper, store } = setupSnowflake((project) => {
      project.root_id = ''
      project.branch_id = ''
    })

    await flushPromises()

    expect(store.loadProgress).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="snowflake-prompt-controls"]').exists()).toBe(true)
  })

  it('shows errors when saving or resetting prompts without context', async () => {
    const { wrapper, projectStore } = setupSnowflake((project) => {
      project.root_id = ''
      project.branch_id = ''
    })

    const saveButton = wrapper.find('[data-test="snowflake-prompt-save"]')
    await saveButton.trigger('click')
    await flushPromises()

    const errorPanel = wrapper.find('[data-test="snowflake-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('root_id')

    projectStore.root_id = 'root-alpha'
    projectStore.branch_id = ''

    const resetButton = wrapper.find('[data-test="snowflake-prompt-reset"]')
    await resetButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="snowflake-error"]').text()).toContain('branch_id')
  })

  it('flags error when saving updates with missing character id', async () => {
    const { wrapper } = setupSnowflake((project, snowflake) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
      snowflake.steps.logline = ['Idea']
      snowflake.steps.root = makeRoot()
      snowflake.steps.characters = [
        {
          name: 'Hero',
          ambition: 'Goal',
          conflict: 'Conflict',
          epiphany: 'Growth',
          voice_dna: 'Voice',
        },
      ]
    })

    const saveButton = wrapper.find('[data-test="save-project-btn"]')
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakeStep).not.toHaveBeenCalled()
    const errorPanel = wrapper.find('[data-test="snowflake-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('character_id')
  })
  it('syncs project context when step4 creates new root', async () => {
    const { wrapper, projectStore } = setupSnowflake((project, snowflake) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
      snowflake.steps.root = makeRoot()
      snowflake.steps.characters = [
        {
          name: 'Hero',
          ambition: 'Goal',
          conflict: 'Conflict',
          epiphany: 'Growth',
          voice_dna: 'Voice',
        },
      ]
    })

    const step4Button = wrapper.find('[data-test="snowflake-step4-submit"]')
    await step4Button.trigger('click')
    await flushPromises()

    expect(projectStore.root_id).toBe('root-9')
    expect(projectStore.branch_id).toBe('branch-9')
  })

  it('shows error when step2 request fails', async () => {
    snowflakeApiMock.fetchSnowflakeStep2.mockRejectedValueOnce(
      new Error('upstream llm request failed with status 429'),
    )

    const { wrapper } = setupSnowflake((project, snowflake) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
      snowflake.steps.logline = ['candidate logline']
      snowflake.steps.root = makeRoot()
    })

    await flushPromises()

    const step2Button = wrapper.find('[data-test="snowflake-step2-submit"]')
    await step2Button.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="snowflake-error"]').text()).toContain('429')
  })

  it('blocks step3 when restored root is incomplete', async () => {
    const { wrapper } = setupSnowflake((project, snowflake) => {
      project.root_id = 'root-2'
      project.branch_id = 'main'
      snowflake.steps.root = {
        ...makeRoot(),
        three_disasters: ['d1'],
      }
    })

    await flushPromises()

    const step3Button = wrapper.find('[data-test="snowflake-step3-submit"]')
    await step3Button.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.fetchSnowflakeStep3).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="snowflake-error"]').text()).toContain('three_disasters')
  })

  it('runs step6 with fallback root id and navigates', async () => {
    const { wrapper } = setupSnowflake((project, snowflake) => {
      project.root_id = 'root-2'
      project.branch_id = 'main'
      snowflake.id = 'root-2'
      snowflake.steps.root = makeRoot()
      snowflake.steps.acts = [
        {
          id: 'act-1',
          root_id: 'root-2',
          sequence: 1,
          title: 'Act 1',
          purpose: 'Purpose',
          tone: 'calm',
        },
      ]
    })

    await flushPromises()

    const step6Button = wrapper.find('[data-test="snowflake-step6-submit"]')
    await step6Button.trigger('click')
    await flushPromises()

    expect(anchorApiMock.anchorApi.generateAnchors).toHaveBeenCalledWith(
      'root-2',
      'main',
      expect.objectContaining({ logline: 'root' }),
      expect.any(Array),
      { prompt: 'p6' },
    )
    expect(routerPushMock).toHaveBeenCalledWith({
      path: '/editor',
      query: { root_id: 'root-2', branch_id: 'main' },
    })
  })
})

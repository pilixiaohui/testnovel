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
  fetchSnowflakePrompts: vi.fn(),
  saveSnowflakePrompts: vi.fn(),
  resetSnowflakePrompts: vi.fn(),
}))

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  fetchSnowflakeStep1: ReturnType<typeof vi.fn>
  fetchSnowflakePrompts: ReturnType<typeof vi.fn>
  saveSnowflakePrompts: ReturnType<typeof vi.fn>
  resetSnowflakePrompts: ReturnType<typeof vi.fn>
  updateSnowflakeLogline: ReturnType<typeof vi.fn>
  updateSnowflakeCharacter: ReturnType<typeof vi.fn>
  updateSnowflakeAct: ReturnType<typeof vi.fn>
  updateSnowflakeChapter: ReturnType<typeof vi.fn>
  updateSnowflakeScene: ReturnType<typeof vi.fn>
}

const promptDefaults = {
  step1: 'Default prompt for step 1',
  step2: 'Default prompt for step 2',
  step3: 'Default prompt for step 3',
  step4: 'Default prompt for step 4',
  step5: 'Default prompt for step 5',
  step6: 'Default prompt for step 6',
}

const setupSnowflake = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')
  const store = useSnowflakeStore()
  store.id = 'root-alpha'
  vi.spyOn(store, 'loadProgress').mockResolvedValue({ step: 1 })
  const wrapper = mount(SnowflakeView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
    },
  })
  return { wrapper, store }
}

describe('M2-T3 snowflake prompt customization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = {}
    snowflakeApiMock.fetchSnowflakePrompts.mockResolvedValue({ ...promptDefaults })
    snowflakeApiMock.saveSnowflakePrompts.mockResolvedValue({ ok: true })
    snowflakeApiMock.resetSnowflakePrompts.mockResolvedValue({ ...promptDefaults })
    snowflakeApiMock.fetchSnowflakeStep1.mockResolvedValue(['Logline'])
  })

  it('renders prompt editors per step with current prompt values', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    expect(snowflakeApiMock.fetchSnowflakePrompts).toHaveBeenCalledWith('root-alpha', 'branch-alpha')

    for (const step of [1, 2, 3, 4, 5, 6]) {
      const input = wrapper.find(`[data-test="snowflake-step${step}-prompt-input"]`)
      expect(input.exists()).toBe(true)
      const value = (input.element as HTMLTextAreaElement).value
      expect(value.length).toBeGreaterThan(0)
    }

    const step1Input = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect((step1Input.element as HTMLTextAreaElement).value).toBe(promptDefaults.step1)
  })

  it('loads prompts even when progress restore fails', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')
    const store = useSnowflakeStore()
    store.id = 'root-alpha'
    vi.spyOn(store, 'loadProgress').mockRejectedValue(new Error('restore failed'))

    const wrapper = mount(SnowflakeView, {
      global: {
        plugins: [pinia],
        stubs: {
          StateExtractPanel: true,
        },
      },
    })

    await flushPromises()

    expect(snowflakeApiMock.fetchSnowflakePrompts).toHaveBeenCalledWith('root-alpha', 'branch-alpha')
    const step1Input = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(step1Input.exists()).toBe(true)
    expect((step1Input.element as HTMLTextAreaElement).value).toBe(promptDefaults.step1)
  })

  it('marks dirty when prompt changes and clears after save', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const promptInput = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(promptInput.exists()).toBe(true)
    await promptInput.setValue('Custom step1 prompt')
    await flushPromises()

    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)

    const saveButton = wrapper.find('[data-test="snowflake-prompt-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakePrompts).toHaveBeenCalledWith(
      'root-alpha',
      'branch-alpha',
      expect.objectContaining({ step1: 'Custom step1 prompt' }),
    )
    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(false)
  })

  it.each([
    { label: 'empty', value: '' },
    { label: 'long', value: 'L'.repeat(1200) },
  ])('saves %s prompt content', async ({ value }) => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const promptInput = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(promptInput.exists()).toBe(true)
    await promptInput.setValue(value)

    const saveButton = wrapper.find('[data-test="snowflake-prompt-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakePrompts).toHaveBeenCalledWith(
      'root-alpha',
      'branch-alpha',
      expect.objectContaining({ step1: value }),
    )
  })

  it('keeps dirty state and shows error when prompt save fails', async () => {
    snowflakeApiMock.saveSnowflakePrompts.mockRejectedValue(new Error('save failed'))

    const { wrapper } = setupSnowflake()
    await flushPromises()

    const promptInput = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(promptInput.exists()).toBe(true)
    await promptInput.setValue('Dirty prompt')
    await flushPromises()

    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)

    const saveButton = wrapper.find('[data-test="snowflake-prompt-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.saveSnowflakePrompts).toHaveBeenCalled()
    expect(wrapper.find('[data-test="snowflake-dirty"]').exists()).toBe(true)
    const errorPanel = wrapper.find('[data-test="snowflake-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text().length).toBeGreaterThan(0)
  })

  it('uses saved prompt on next generation', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const promptInput = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(promptInput.exists()).toBe(true)
    await promptInput.setValue('Custom prompt for step1')

    const saveButton = wrapper.find('[data-test="snowflake-prompt-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    const ideaInput = wrapper.find('[data-test="snowflake-idea-input"]')
    expect(ideaInput.exists()).toBe(true)
    await ideaInput.setValue('Idea')

    const runButton = wrapper.find('[data-test="snowflake-step1-submit"]')
    expect(runButton.exists()).toBe(true)
    await runButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.fetchSnowflakeStep1).toHaveBeenCalledWith(
      'Idea',
      expect.objectContaining({ prompt: 'Custom prompt for step1' }),
    )
  })

  it('resets prompt to default value', async () => {
    const { wrapper } = setupSnowflake()
    await flushPromises()

    const promptInput = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(promptInput.exists()).toBe(true)
    const defaultValue = (promptInput.element as HTMLTextAreaElement).value
    await promptInput.setValue('Custom prompt for reset')

    const resetButton = wrapper.find('[data-test="snowflake-prompt-reset"]')
    expect(resetButton.exists()).toBe(true)
    await resetButton.trigger('click')
    await flushPromises()

    expect(snowflakeApiMock.resetSnowflakePrompts).toHaveBeenCalledWith('root-alpha', 'branch-alpha')
    expect((promptInput.element as HTMLTextAreaElement).value).toBe(defaultValue)
  })
  it('reloads prompts when project context changes in-place', async () => {
    const { wrapper, store } = setupSnowflake()
    vi.spyOn(store, 'loadProgress').mockResolvedValue({ step: 1 })

    snowflakeApiMock.fetchSnowflakePrompts
      .mockResolvedValueOnce({ ...promptDefaults, step1: 'Root A prompt' })
      .mockResolvedValueOnce({ ...promptDefaults, step1: 'Root B prompt' })

    await flushPromises()

    const projectStore = useProjectStore()
    projectStore.setCurrentProject('root-beta', 'branch-beta', '')
    await flushPromises()

    const step1Input = wrapper.find('[data-test="snowflake-step1-prompt-input"]')
    expect(step1Input.exists()).toBe(true)
    expect((step1Input.element as HTMLTextAreaElement).value).toBe('Root B prompt')
    expect(snowflakeApiMock.fetchSnowflakePrompts).toHaveBeenCalledWith('root-beta', 'branch-beta')
  })
})
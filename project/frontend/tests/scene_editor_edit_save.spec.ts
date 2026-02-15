import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useEditorStore } from '@/stores/editor'
import EditorView from '../src/views/EditorView.vue'
import * as sceneApi from '@/api/scene'
import * as branchApi from '@/api/branch'
import * as snowflakeApi from '@/api/snowflake'
import * as chapterApi from '@/api/chapter'
import * as commitApi from '@/api/commit'

const routeState = vi.hoisted(() => ({
  params: { sceneId: 'scene-alpha' },
  query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
  renderScene: vi.fn(),
  updateScene: vi.fn(),
  diffScene: vi.fn(),
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
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
}))

vi.mock('@/api/chapter', () => ({
  renderChapter: vi.fn(),
  reviewChapter: vi.fn(),
}))

vi.mock('@/api/commit', () => ({
  commitApi: {
    commitScene: vi.fn(),
  },
}))

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
  renderScene: ReturnType<typeof vi.fn>
  updateScene: ReturnType<typeof vi.fn>
  diffScene: ReturnType<typeof vi.fn>
}

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

const commitApiMock = vi.mocked(commitApi) as unknown as {
  commitApi: {
    commitScene: ReturnType<typeof vi.fn>
  }
}

const setupEditor = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(EditorView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
    },
  })
  const store = useEditorStore()
  return { wrapper, store }
}

const createDeferred = <T>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('M2-T1 scene editor edit/save', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = 'scene-alpha'
    routeState.query = { root_id: 'root-alpha', branch_id: 'branch-alpha' }
    branchApiMock.branchApi.listBranches.mockResolvedValue(['main'])
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    vi.mocked(chapterApi).renderChapter.mockResolvedValue({ rendered_content: '' })
    commitApiMock.commitApi.commitScene.mockResolvedValue({
      commit_id: 'commit-alpha',
      scene_version_ids: [],
    })
  })

  it('loads scene content, edits summary, and saves update', async () => {
    sceneApiMock.fetchSceneContext.mockResolvedValue({
      id: 'scene-alpha',
      title: 'Loaded title',
      summary: 'Loaded summary',
      outcome: 'success',
    })
    sceneApiMock.renderScene.mockResolvedValue({ content: 'Rendered' })
    sceneApiMock.updateScene.mockResolvedValue({ id: 'scene-alpha' })

    const { wrapper, store } = setupEditor()

    const loadButton = wrapper.find('[data-test="scene-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')
    await flushPromises()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    expect(summaryInput.exists()).toBe(true)
    expect((summaryInput.element as HTMLTextAreaElement).value).toBe('Loaded summary')

    await summaryInput.setValue('Updated summary')
    expect(store.summary).toBe('Updated summary')
    expect(store.is_dirty).toBe(true)
    expect(wrapper.find('[data-test="scene-dirty"]').exists()).toBe(true)

    const saveButton = wrapper.find('[data-test="scene-save"]')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.updateScene).toHaveBeenCalledWith('scene-alpha', 'branch-alpha', {
      outcome: store.outcome,
      summary: 'Updated summary',
    })
    expect(commitApiMock.commitApi.commitScene).toHaveBeenCalledWith(
      'root-alpha',
      'branch-alpha',
      expect.objectContaining({
        scene_origin_id: 'scene-alpha',
        content: expect.objectContaining({ expected_outcome: 'Updated summary' }),
      }),
    )
    expect(store.is_dirty).toBe(false)
    expect(store.last_saved_at.length).toBeGreaterThan(0)
    expect(wrapper.find('[data-test="scene-dirty"]').exists()).toBe(false)
  })

  it('blocks save when summary is empty', async () => {
    const { wrapper } = setupEditor()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    await summaryInput.setValue('')

    const saveButton = wrapper.find('[data-test="scene-save"]')
    await saveButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.updateScene).not.toHaveBeenCalled()

    const errorPanel = wrapper.find('[data-test="scene-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('Summary is required.')
  })

  it('saves long summary content', async () => {
    const longSummary = 'L'.repeat(1200)
    sceneApiMock.updateScene.mockResolvedValue({ id: 'scene-alpha' })

    const { wrapper, store } = setupEditor()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    await summaryInput.setValue(longSummary)

    const saveButton = wrapper.find('[data-test="scene-save"]')
    await saveButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.updateScene).toHaveBeenCalledWith('scene-alpha', 'branch-alpha', {
      outcome: store.outcome,
      summary: longSummary,
    })
  })

  it('shows error and keeps dirty when save fails', async () => {
    sceneApiMock.updateScene.mockRejectedValue(new Error('save failed'))

    const { wrapper, store } = setupEditor()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    await summaryInput.setValue('Dirty summary')
    expect(store.is_dirty).toBe(true)

    const saveButton = wrapper.find('[data-test="scene-save"]')
    await saveButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.updateScene).toHaveBeenCalled()
    expect(store.is_dirty).toBe(true)
    expect(store.last_saved_at).toBe('')

    const errorPanel = wrapper.find('[data-test="scene-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('Failed to save scene.')
  })

  it('toggles saving state while save request in flight', async () => {
    const deferred = createDeferred<{ id: string }>()
    sceneApiMock.updateScene.mockImplementation(() => deferred.promise)

    const { wrapper, store } = setupEditor()

    const summaryInput = wrapper.find('[data-test="scene-summary-input"]')
    await summaryInput.setValue('Saving summary')

    const saveButton = wrapper.find('[data-test="scene-save"]')
    const saveTask = saveButton.trigger('click')
    await flushPromises()

    const savingFlag = (store as { is_saving?: boolean }).is_saving
    expect(savingFlag).toBe(true)

    deferred.resolve({ id: 'scene-alpha' })
    await saveTask
    await flushPromises()

    const savingAfter = (store as { is_saving?: boolean }).is_saving
    expect(savingAfter).toBe(false)
  })
})

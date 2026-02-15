import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflakeStore } from '@/stores/snowflake'
import EditorView from '../src/views/EditorView.vue'
import * as sceneApi from '@/api/scene'
import * as branchApi from '@/api/branch'
import * as snowflakeApi from '@/api/snowflake'
import * as chapterApi from '@/api/chapter'

const routeState = vi.hoisted(() => ({
  params: { sceneId: 'scene-alpha' },
  query: { root_id: 'root-alpha', branch_id: 'main' },
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

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  diffScene: ReturnType<typeof vi.fn>
  renderScene: ReturnType<typeof vi.fn>
}

const branchApiMock = vi.mocked(branchApi) as unknown as {
  branchApi: {
    listBranches: ReturnType<typeof vi.fn>
    switchBranch: ReturnType<typeof vi.fn>
    getBranchHistory: ReturnType<typeof vi.fn>
    getRootSnapshot: ReturnType<typeof vi.fn>
    resetBranch: ReturnType<typeof vi.fn>
  }
}

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  snowflakeApi: {
    listActs: ReturnType<typeof vi.fn>
    listChapters: ReturnType<typeof vi.fn>
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
  const snowflakeStore = useSnowflakeStore()
  return { wrapper, snowflakeStore }
}

describe('EditorView branch coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = 'scene-alpha'
    routeState.query = { root_id: 'root-alpha', branch_id: 'main' }
    branchApiMock.branchApi.listBranches.mockResolvedValue(['main'])
    branchApiMock.branchApi.switchBranch.mockResolvedValue({ branch_id: 'main' })
    branchApiMock.branchApi.getBranchHistory.mockResolvedValue([])
    branchApiMock.branchApi.getRootSnapshot.mockResolvedValue({ id: 'snapshot-1' })
    branchApiMock.branchApi.resetBranch.mockResolvedValue({ ok: true })
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    sceneApiMock.diffScene.mockResolvedValue({ diff: '' })
    sceneApiMock.renderScene.mockResolvedValue({ content: 'rendered' })
    vi.mocked(chapterApi).renderChapter.mockResolvedValue({ rendered_content: '' })
    vi.mocked(chapterApi).reviewChapter.mockResolvedValue({ review_status: 'approved' })
  })

  it('updates current and selected branch when list does not include defaults', async () => {
    branchApiMock.branchApi.listBranches.mockResolvedValue(['dev'])

    const { wrapper } = setupEditor()
    await flushPromises()

    expect(wrapper.find('[data-test="branch-current"]').text()).toContain('dev')
    const select = wrapper.find('[data-test="branch-switch-select"]')
    expect((select.element as HTMLSelectElement).value).toBe('dev')
  })

  it('shows error when branch list is invalid', async () => {
    branchApiMock.branchApi.listBranches.mockResolvedValue({} as unknown as string[])

    const { wrapper } = setupEditor()
    await flushPromises()

    const errorPanel = wrapper.find('[data-test="scene-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('Failed to load branches.')
  })

  it('falls back to selected branch when switch response is empty', async () => {
    branchApiMock.branchApi.listBranches.mockResolvedValue(['main', 'dev'])
    branchApiMock.branchApi.switchBranch.mockResolvedValue({})

    const { wrapper } = setupEditor()
    await flushPromises()

    const select = wrapper.find('[data-test="branch-switch-select"]')
    await select.setValue('dev')

    const switchButton = wrapper.find('[data-test="branch-switch"]')
    await switchButton.trigger('click')
    await flushPromises()

    expect(branchApiMock.branchApi.switchBranch).toHaveBeenCalledWith('root-alpha', 'dev')
    expect(wrapper.find('[data-test="branch-current"]').text()).toContain('dev')
  })

  it('normalizes commit history and wires diff range', async () => {
    branchApiMock.branchApi.getBranchHistory.mockResolvedValue({
      data: [{ id: 'c1' }, { id: 'c2' }],
    })
    sceneApiMock.diffScene.mockResolvedValue({ diff: 'DIFF' })

    const { wrapper } = setupEditor()
    await flushPromises()

    const historyButton = wrapper.find('[data-test="commit-history-load"]')
    await historyButton.trigger('click')
    await flushPromises()

    const diffButton = wrapper.find('[data-test="scene-diff"]')
    await diffButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.diffScene).toHaveBeenCalledWith('scene-alpha', 'main', 'c2', 'c1')
  })

  it('uses empty diff range when history is too short', async () => {
    branchApiMock.branchApi.getBranchHistory.mockResolvedValue([{ id: 'solo' }])

    const { wrapper } = setupEditor()
    await flushPromises()

    const historyButton = wrapper.find('[data-test="commit-history-load"]')
    await historyButton.trigger('click')
    await flushPromises()

    const diffButton = wrapper.find('[data-test="scene-diff"]')
    await diffButton.trigger('click')
    await flushPromises()

    expect(sceneApiMock.diffScene).toHaveBeenCalledWith('scene-alpha', 'main', '', '')
  })

  it('sets error when diff or render is invoked without a scene id', async () => {
    routeState.params.sceneId = ''

    const { wrapper } = setupEditor()

    await (wrapper.vm as unknown as { diffSceneView: () => Promise<void> }).diffSceneView()
    expect(wrapper.find('[data-test="scene-error"]').text()).toContain('Scene ID is required.')

    await (wrapper.vm as unknown as { renderSceneView: () => Promise<void> }).renderSceneView()
    expect(wrapper.find('[data-test="scene-error"]').text()).toContain('Scene ID is required.')
  })

  it('renders chapter error and review failure branches', async () => {
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([{ id: 'act-1' }])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([
      {
        id: 'chapter-1',
        sequence: 1,
        title: 'Intro',
        review_status: 'pending',
      },
    ])
    vi.mocked(chapterApi).renderChapter.mockRejectedValue(new Error('render failed'))
    vi.mocked(chapterApi).reviewChapter.mockResolvedValue({})

    const { wrapper } = setupEditor()
    await flushPromises()

    const renderButton = wrapper.find('[data-test="chapter-render"]')
    await renderButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="chapter-render-error"]').exists()).toBe(true)

    const approveButton = wrapper.find('[data-test="chapter-approve"]')
    await approveButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="scene-error"]').text()).toContain('Failed to review chapter.')
  })
})

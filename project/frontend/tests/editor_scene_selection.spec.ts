import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import EditorView from '../src/views/EditorView.vue'
import { fetchScenes } from '@/api/scene'
import * as branchApi from '@/api/branch'
import * as snowflakeApi from '@/api/snowflake'
import * as chapterApi from '@/api/chapter'

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

const fetchScenesMock = vi.mocked(fetchScenes)

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

const chapterApiMock = vi.mocked(chapterApi) as unknown as {
  renderChapter: ReturnType<typeof vi.fn>
}

describe('M1-T2 editor scene selection', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = { root_id: 'root-alpha', branch_id: 'branch-alpha' }
    branchApiMock.branchApi.listBranches.mockResolvedValue(['main'])
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])
    chapterApiMock.renderChapter.mockResolvedValue({ rendered_content: '' })
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

    const wrapper = mount(EditorView, {
      global: {
        plugins: [pinia],
        stubs: {
          StateExtractPanel: true,
        },
      },
    })

    await flushPromises()

    expect(fetchScenesMock).toHaveBeenCalledWith('root-alpha', 'branch-alpha')

    const select = wrapper.find('[data-test="scene-select"]')
    expect(select.exists()).toBe(true)
    await select.setValue('scene-beta')
    await flushPromises()

    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'editor',
      params: { sceneId: 'scene-beta' },
      query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
    })
    expect(projectStore.scene_id).toBe('scene-beta')
  })
})

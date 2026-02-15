import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import EditorView from '../src/views/EditorView.vue'
import * as sceneApi from '@/api/scene'
import * as branchApi from '@/api/branch'
import * as snowflakeApi from '@/api/snowflake'
import * as chapterApi from '@/api/chapter'

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

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchScenes: ReturnType<typeof vi.fn>
  fetchSceneContext: ReturnType<typeof vi.fn>
  renderScene: ReturnType<typeof vi.fn>
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

const chapterApiMock = vi.mocked(chapterApi) as unknown as {
  renderChapter: ReturnType<typeof vi.fn>
}

describe('EditorView scene context sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.sceneId = 'scene-alpha'
    routeState.query = { root_id: 'root-alpha', branch_id: 'branch-alpha' }
    branchApiMock.branchApi.listBranches.mockResolvedValue(['main'])
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])
    chapterApiMock.renderChapter.mockResolvedValue({ rendered_content: '' })
    sceneApiMock.fetchScenes.mockResolvedValue({ scenes: [] })
    sceneApiMock.fetchSceneContext.mockResolvedValue({
      id: 'scene-alpha',
      title: 'Loaded title',
      summary: 'Loaded summary',
      outcome: 'success',
      content: 'Loaded content',
    })
    sceneApiMock.renderScene.mockResolvedValue({ content: 'Rendered' })
  })

  it('syncs projectStore.scene_id after loading scene context', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const projectStore = useProjectStore()
    projectStore.setProject('root-alpha', 'branch-alpha', '')

    const wrapper = mount(EditorView, {
      global: {
        plugins: [pinia],
        stubs: {
          StateExtractPanel: true,
        },
      },
    })

    const loadButton = wrapper.find('[data-test="scene-load"]')
    expect(loadButton.exists()).toBe(true)
    await loadButton.trigger('click')
    await flushPromises()

    expect(projectStore.scene_id).toBe('scene-alpha')
  })
})

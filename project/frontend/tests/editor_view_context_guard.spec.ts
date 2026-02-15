import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import EditorView from '../src/views/EditorView.vue'

const routeState = vi.hoisted(() => ({
  name: 'editor',
  params: {},
  query: {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const listBranchesMock = vi.hoisted(() => vi.fn())
const listActsMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: listBranchesMock,
    switchBranch: vi.fn(),
    getBranchHistory: vi.fn(),
    getRootSnapshot: vi.fn(),
    resetBranch: vi.fn(),
  },
}))

vi.mock('@/api/snowflake', () => ({
  snowflakeApi: {
    listActs: listActsMock,
    listChapters: vi.fn(),
  },
}))

vi.mock('@/api/scene', () => ({
  fetchScenes: vi.fn(),
  fetchSceneContext: vi.fn(),
  updateScene: vi.fn(),
  diffScene: vi.fn(),
  renderScene: vi.fn(),
}))

vi.mock('@/api/chapter', () => ({
  renderChapter: vi.fn(),
  reviewChapter: vi.fn(),
}))

describe('EditorView context guard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = {}
  })

  it('renders context-missing state without throwing when project context is absent', async () => {
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

    await flushPromises()

    expect(wrapper.find('[data-test="scene-list-context-missing"]').exists()).toBe(true)
    expect(listBranchesMock).not.toHaveBeenCalled()
    expect(listActsMock).not.toHaveBeenCalled()
  })
})

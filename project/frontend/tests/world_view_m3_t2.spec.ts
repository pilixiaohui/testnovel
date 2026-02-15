import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import WorldView from '../src/views/WorldView.vue'
import * as projectApi from '@/api/project'
import * as entityApi from '@/api/entity'
import * as anchorApi from '@/api/anchor'
import * as subplotApi from '@/api/subplot'

const routeState = vi.hoisted(() => ({
  name: 'world',
  params: { sceneId: '', rootId: '', branchId: '' },
  query: {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

vi.mock('@/api/project', () => ({
  fetchProjects: vi.fn(),
  createProject: vi.fn(),
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: vi.fn(),
  fetchRelations: vi.fn(),
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: vi.fn(),
}))

const projectApiMock = vi.mocked(projectApi) as unknown as {
  fetchProjects: ReturnType<typeof vi.fn>
}

const entityApiMock = vi.mocked(entityApi) as unknown as {
  fetchEntities: ReturnType<typeof vi.fn>
  fetchRelations: ReturnType<typeof vi.fn>
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  fetchAnchors: ReturnType<typeof vi.fn>
}

const subplotApiMock = vi.mocked(subplotApi) as unknown as {
  fetchSubplots: ReturnType<typeof vi.fn>
}

const makeWorlds = () => [
  {
    root_id: 'root-alpha',
    name: 'World Alpha',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-02T10:00:00Z',
  },
  {
    root_id: 'root-2',
    name: 'World Beta',
    created_at: '2025-01-03T10:00:00Z',
    updated_at: '2025-01-04T10:00:00Z',
  },
]

const mountWorldView = (options: { rootId?: string; branchId?: string } = {}) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  projectStore.root_id = options.rootId ?? 'root-store'
  projectStore.branch_id = options.branchId ?? 'branch-store'

  const errors: unknown[] = []
  const wrapper = mount(WorldView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
      config: {
        errorHandler: (err) => {
          errors.push(err)
        },
      },
    },
  })

  return { wrapper, projectStore, errors }
}

describe('M3-T2 WorldView integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = { sceneId: '', rootId: '', branchId: '' }
    routeState.query = { root_id: 'root-route', branch_id: 'branch-route' }
    projectApiMock.fetchProjects.mockResolvedValue({ roots: [] })
    entityApiMock.fetchEntities.mockResolvedValue([])
    entityApiMock.fetchRelations.mockResolvedValue([])
    anchorApiMock.fetchAnchors.mockResolvedValue([])
    subplotApiMock.fetchSubplots.mockResolvedValue([])
  })

  it('M3-T2 loads world list from API and renders items', async () => {
    const roots = makeWorlds()
    projectApiMock.fetchProjects.mockResolvedValue({ roots })

    const { wrapper } = mountWorldView({ rootId: 'root-alpha', branchId: 'main' })

    await flushPromises()

    expect(projectApiMock.fetchProjects).toHaveBeenCalled()
    const list = wrapper.find('[data-test="world-list"]')
    expect(list.exists()).toBe(true)
    expect(list.text()).toContain('World Alpha')
    expect(list.text()).toContain('World Beta')
  })

  it('M3-T2 loads entities, anchors, and relations after selecting a world', async () => {
    const roots = makeWorlds()
    projectApiMock.fetchProjects.mockResolvedValue({ roots })

    const { wrapper } = mountWorldView({ rootId: 'root-alpha', branchId: 'main' })

    await flushPromises()

    const worldItem = wrapper.find('[data-test="world-list-item"]')
    expect(worldItem.exists()).toBe(true)
    await worldItem.trigger('click')
    await flushPromises()

    expect(entityApiMock.fetchEntities).toHaveBeenCalledWith('root-alpha', 'main')
    expect(anchorApiMock.fetchAnchors).toHaveBeenCalledWith('root-alpha', 'main')
    expect(entityApiMock.fetchRelations).toHaveBeenCalledWith('root-alpha', 'main')

    expect(wrapper.findComponent({ name: 'EntityList' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AnchorTimeline' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'RelationGraph' }).exists()).toBe(true)
  })

  it('M3-T2 shows empty state when no worlds returned', async () => {
    projectApiMock.fetchProjects.mockResolvedValue({ roots: [] })

    const { wrapper } = mountWorldView()

    await flushPromises()

    expect(wrapper.find('[data-test="world-list-empty"]').exists()).toBe(true)
  })

  it('M3-T2 shows error state when world list API fails', async () => {
    projectApiMock.fetchProjects.mockRejectedValue(new Error('network error'))

    const { wrapper } = mountWorldView()

    await flushPromises()

    expect(wrapper.find('[data-test="world-error"]').exists()).toBe(true)
  })
})

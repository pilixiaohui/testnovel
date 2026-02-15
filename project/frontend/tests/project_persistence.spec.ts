import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { apiClient } from '@/api/index'
import HomeView from '../src/views/HomeView.vue'

const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

vi.mock('@/api/index', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    defaults: { baseURL: '/api/v1' },
  },
}))

const apiClientMock = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

const makeProjects = () => [
  {
    root_id: 'root-alpha',
    name: 'Project Alpha',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-02T10:00:00Z',
  },
  {
    root_id: 'root-2',
    name: 'Project Beta',
    created_at: '2025-02-01T10:00:00Z',
    updated_at: '2025-02-02T10:00:00Z',
  },
]

const mountHomeView = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(HomeView, { global: { plugins: [pinia] } })
  const store = useProjectStore()
  return { wrapper, store }
}

describe('project persistence contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('loads project list from API and renders cards', async () => {
    const roots = makeProjects()
    apiClientMock.get.mockResolvedValue({ roots })

    const { wrapper } = mountHomeView()
    await flushPromises()

    expect(apiClientMock.get).toHaveBeenCalledWith('/roots')
    const cards = wrapper.findAll('[data-test="project-card"]')
    expect(cards.length).toBe(roots.length)
    roots.forEach((project) => {
      expect(wrapper.text()).toContain(project.name)
    })
  })

  it('shows empty state when project list is empty', async () => {
    apiClientMock.get.mockResolvedValue({ roots: [] })

    const { wrapper } = mountHomeView()
    await flushPromises()

    expect(wrapper.find('[data-test="project-list-empty"]').exists()).toBe(true)
  })

  it('exposes error state when project list API fails', async () => {
    const store = useProjectStore()
    apiClientMock.get.mockRejectedValue(new Error('network error'))

    await expect(store.listProjects()).rejects.toThrow('network error')

    const errorMessage = (store as { project_list_error?: string }).project_list_error
    expect(errorMessage).toBe('network error')
  })

  it('exposes timeout state when project list API times out', async () => {
    const store = useProjectStore()
    apiClientMock.get.mockRejectedValue(new Error('timeout'))

    await expect(store.listProjects()).rejects.toThrow('timeout')

    const errorMessage = (store as { project_list_error?: string }).project_list_error
    expect(errorMessage).toBe('timeout')
  })

  it('saveProject persists new project to backend and updates list', async () => {
    const store = useProjectStore()
    const newProject = {
      root_id: 'root-9',
      name: 'Project Gamma',
      created_at: '2025-03-01T10:00:00Z',
      updated_at: '2025-03-01T10:00:00Z',
    }

    apiClientMock.post.mockResolvedValue(newProject)

    const saveProject = store.saveProject as unknown as (payload: { name: string }) => Promise<void>
    await saveProject({ name: newProject.name })

    expect(apiClientMock.post).toHaveBeenCalledWith('/roots', { name: newProject.name })
    expect(store.projects).toContainEqual(newProject)
  })

  it.each([
    { label: 'empty', name: '' },
    { label: 'too-long', name: 'x'.repeat(256) },
  ])('saveProject rejects invalid name: $label', async ({ name }) => {
    const store = useProjectStore()
    const saveProject = store.saveProject as unknown as (payload: { name: string }) => Promise<void>

    await expect(saveProject({ name })).rejects.toThrow()
  })
})

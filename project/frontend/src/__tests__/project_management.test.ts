import { beforeEach, describe, expect, it, vi } from 'vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import HomeView from '../views/HomeView.vue'
import { useProjectStore } from '../stores/project'
import { branchApi } from '@/api/branch'
import { createProject, deleteProject, fetchProject, fetchProjects } from '@/api/project'

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn(),
    createBranch: vi.fn(),
    switchBranch: vi.fn(),
  },
}))

vi.mock('@/api/project', () => ({
  fetchProjects: vi.fn(),
  fetchProject: vi.fn(),
  createProject: vi.fn(),
  deleteProject: vi.fn(),
}))

const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0))

const ButtonStub = {
  inheritAttrs: false,
  template: '<button v-bind="$attrs"><slot /></button>',
}

const CardStub = {
  inheritAttrs: false,
  template: '<div v-bind="$attrs"><slot name="header" /><slot /></div>',
}

describe('project store persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('setProject persists project identifiers to localStorage', () => {
    const store = useProjectStore()
    store.setProject('root-alpha', 'branch-alpha', 'scene-alpha')

    expect(store.root_id).toBe('root-alpha')
    expect(store.branch_id).toBe('branch-alpha')
    expect(store.scene_id).toBe('scene-alpha')
    expect(localStorage.getItem('project_root_id')).toBe('root-alpha')
    expect(localStorage.getItem('project_branch_id')).toBe('branch-alpha')
    expect(localStorage.getItem('project_scene_id')).toBe('scene-alpha')
  })

  it('clearProject resets identifiers and localStorage', () => {
    const store = useProjectStore()
    store.setProject('root-alpha', 'branch-alpha', 'scene-alpha')
    store.clearProject()

    expect(store.root_id).toBe('')
    expect(store.branch_id).toBe('main')
    expect(store.scene_id).toBe('')
    expect(localStorage.getItem('project_root_id')).toBeNull()
    expect(localStorage.getItem('project_branch_id')).toBeNull()
    expect(localStorage.getItem('project_scene_id')).toBeNull()
  })

  it('loads branches and updates current branch', async () => {
    const store = useProjectStore()
    const listBranchesMock = vi.mocked(branchApi.listBranches)
    const createBranchMock = vi.mocked(branchApi.createBranch)
    const switchBranchMock = vi.mocked(branchApi.switchBranch)

    listBranchesMock.mockResolvedValue(['main', 'feature-alpha'])
    const branches = await store.loadBranches('root-alpha')
    expect(branches).toEqual(['main', 'feature-alpha'])
    expect(store.branches).toEqual(['main', 'feature-alpha'])

    createBranchMock.mockResolvedValue({ root_id: 'root-alpha', branch_id: 'feature-beta' })
    await store.createBranch('root-alpha', 'feature-beta')
    expect(store.branch_id).toBe('feature-beta')
    expect(store.branches).toContain('feature-beta')
    expect(localStorage.getItem('project_branch_id')).toBe('feature-beta')

    switchBranchMock.mockResolvedValue({ root_id: 'root-alpha', branch_id: 'feature-gamma' })
    await store.switchBranch('root-alpha', 'feature-gamma')
    expect(store.branch_id).toBe('feature-gamma')
    expect(localStorage.getItem('project_branch_id')).toBe('feature-gamma')
  })
})

describe('HomeView project management', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders list, creates, and deletes projects', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const fetchProjectsMock = vi.mocked(fetchProjects)
    const fetchProjectMock = vi.mocked(fetchProject)
    const createProjectMock = vi.mocked(createProject)
    const deleteProjectMock = vi.mocked(deleteProject)

    fetchProjectsMock.mockResolvedValue({
      roots: [
        { root_id: 'root-alpha', name: 'Alpha', created_at: 'now', updated_at: 'later' },
      ],
    })
    createProjectMock.mockResolvedValue({
      root_id: 'root-beta',
      name: 'Beta',
      created_at: 'now',
      updated_at: 'later',
    })
    fetchProjectMock.mockResolvedValue({
      root_id: 'root-beta',
      branch_id: 'main',
      scene_id: '',
      name: 'Beta',
      logline: 'logline',
      created_at: 'now',
      updated_at: 'later',
    })
    deleteProjectMock.mockResolvedValue({ success: true })

    const wrapper = mount(HomeView, {
      global: {
        plugins: [pinia],
        stubs: {
          'el-button': ButtonStub,
          'el-card': CardStub,
          'el-tag': true,
          'el-empty': true,
          'el-descriptions': true,
          'el-descriptions-item': true,
          'el-row': true,
          'el-col': true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.findAll('[data-test="project-card"]').length).toBe(1)

    const input = wrapper.get('[data-test="project-create-input"]')
    await input.setValue('Beta')
    await wrapper.get('[data-test="create-project-btn"]').trigger('click')
    await flushPromises()

    expect(createProjectMock).toHaveBeenCalledWith('Beta')
    expect(fetchProjectMock).toHaveBeenCalledWith('root-beta', 'main')
    expect(pushMock).toHaveBeenCalledWith('/snowflake')
    expect(wrapper.findAll('[data-test="project-card"]').length).toBe(2)

    const deleteButtons = wrapper.findAll('[data-test="project-delete"]')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(deleteProjectMock).toHaveBeenCalledWith('root-alpha')
    expect(wrapper.findAll('[data-test="project-card"]').length).toBe(1)
  })

  it('loads project detail before navigating to snowflake', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const fetchProjectsMock = vi.mocked(fetchProjects)
    const fetchProjectMock = vi.mocked(fetchProject)

    fetchProjectsMock.mockResolvedValue({
      roots: [
        { root_id: 'root-alpha', name: 'Alpha', created_at: 'now', updated_at: 'later' },
      ],
    })
    fetchProjectMock.mockResolvedValue({
      root_id: 'root-alpha',
      branch_id: 'main',
      scene_id: '',
      name: 'Alpha',
      logline: 'logline',
      created_at: 'now',
      updated_at: 'later',
    })

    const wrapper = mount(HomeView, {
      global: {
        plugins: [pinia],
        stubs: {
          'el-button': ButtonStub,
          'el-card': CardStub,
          'el-tag': true,
          'el-empty': true,
          'el-descriptions': true,
          'el-descriptions-item': true,
          'el-row': true,
          'el-col': true,
        },
      },
    })

    await flushPromises()

    const cards = wrapper.findAll('[data-test="project-card"]')
    expect(cards.length).toBe(1)

    await cards[0].trigger('click')
    await flushPromises()

    expect(fetchProjectMock).toHaveBeenCalledWith('root-alpha', 'main')
    expect(pushMock).toHaveBeenCalledWith('/snowflake')
  })
})

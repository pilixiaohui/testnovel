import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'

const ROOT_ID_STORAGE_KEY = 'project_root_id'
const DEFAULT_BRANCH_ID = 'main'

const fetchProjectsMock = vi.hoisted(() => vi.fn())
const fetchProjectMock = vi.hoisted(() => vi.fn())

vi.mock(
  '@/api/project',
  () => ({
    fetchProjects: fetchProjectsMock,
    fetchProject: fetchProjectMock,
  }),
  { virtual: true },
)

const assertAction = <T extends (...args: any[]) => Promise<unknown>>(
  action: unknown,
  name: string,
): T => {
  if (typeof action !== 'function') {
    throw new Error(`Expected action "${name}" to be a function`)
  }
  return action as T
}

const makeRoots = () => [
  {
    root_id: 'root-alpha',
    name: 'Project Alpha',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-02T10:00:00Z',
  },
  {
    root_id: 'root-2',
    name: 'Project Beta',
    created_at: '2025-01-03T10:00:00Z',
    updated_at: '2025-01-04T10:00:00Z',
  },
]

describe('project store contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('listProjects calls API and updates projects', async () => {
    const roots = makeRoots()
    fetchProjectsMock.mockResolvedValue({ roots })

    const store = useProjectStore()
    const listProjects = assertAction<() => Promise<void>>(store.listProjects, 'listProjects')
    await listProjects()

    expect(fetchProjectsMock).toHaveBeenCalled()
    expect(store.projects).toEqual(roots)
  })

  it('clears stale project context when current root is missing from project list', async () => {
    const roots = makeRoots()
    fetchProjectsMock.mockResolvedValue({ roots })

    const store = useProjectStore()
    store.setProject('root-missing', 'branch-stale', 'scene-stale')

    const listProjects = assertAction<() => Promise<void>>(store.listProjects, 'listProjects')
    await listProjects()

    expect(store.root_id).toBe('')
    expect(store.branch_id).toBe(DEFAULT_BRANCH_ID)
    expect(store.scene_id).toBe('')
    expect(localStorage.getItem(ROOT_ID_STORAGE_KEY)).toBeNull()
  })

  it('loadProject sets root_id and branch_id', async () => {
    const store = useProjectStore()
    fetchProjectMock.mockResolvedValue({
      root_id: 'root-alpha',
      branch_id: DEFAULT_BRANCH_ID,
      scene_id: '',
    })
    const loadProject = assertAction<(rootId: string) => Promise<void>>(store.loadProject, 'loadProject')
    await loadProject('root-alpha')

    expect(fetchProjectMock).toHaveBeenCalledWith('root-alpha', DEFAULT_BRANCH_ID)
    expect(store.root_id).toBe('root-alpha')
    expect(store.branch_id).toBe(DEFAULT_BRANCH_ID)
  })

  it('loadProject throws when payload is invalid', async () => {
    const store = useProjectStore()
    const loadProject = assertAction<(rootId: string) => Promise<void>>(store.loadProject, 'loadProject')
    const invalidPayloads = [null, undefined, 'invalid', 42]

    for (const payload of invalidPayloads) {
      fetchProjectMock.mockResolvedValueOnce(payload as unknown as object)
      await expect(loadProject('root-alpha')).rejects.toThrow('project payload is required')
    }
  })

  it('loadProject persists root_id to localStorage', async () => {
    const store = useProjectStore()
    fetchProjectMock.mockResolvedValue({
      root_id: 'root-9',
      branch_id: DEFAULT_BRANCH_ID,
      scene_id: '',
    })
    const loadProject = assertAction<(rootId: string) => Promise<void>>(store.loadProject, 'loadProject')
    await loadProject('root-9')

    expect(localStorage.getItem(ROOT_ID_STORAGE_KEY)).toBe('root-9')
  })

  it('store restores root_id from localStorage on init', () => {
    localStorage.setItem(ROOT_ID_STORAGE_KEY, 'root-42')

    const store = useProjectStore()
    expect(store.root_id).toBe('root-42')
  })
})

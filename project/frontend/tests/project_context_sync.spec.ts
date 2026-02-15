import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import { setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'

type RouteContext = {
  name?: string
  params: Record<string, string | undefined>
  query: Record<string, string | undefined>
}

const ROOT_ID_STORAGE_KEY = 'project_root_id'
const BRANCH_ID_STORAGE_KEY = 'project_branch_id'
const SCENE_ID_STORAGE_KEY = 'project_scene_id'

const assertAction = <T extends (...args: any[]) => unknown>(action: unknown, name: string): T => {
  if (typeof action !== 'function') {
    throw new Error(`Expected action "${name}" to be a function`)
  }
  return action as T
}

const setupPinia = () => {
  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })
  setActivePinia(pinia)
  return pinia
}

const makeRoute = (overrides: Partial<RouteContext> = {}): RouteContext => ({
  name: 'snowflake',
  params: {},
  query: {},
  ...overrides,
})

describe('projectStore sync context', () => {
  beforeEach(() => {
    setupPinia()
    localStorage.clear()
  })

  it('project context restores root_id/branch_id/scene_id from localStorage', () => {
    localStorage.setItem(ROOT_ID_STORAGE_KEY, 'root-alpha')
    localStorage.setItem(BRANCH_ID_STORAGE_KEY, 'branch-alpha')
    localStorage.setItem(SCENE_ID_STORAGE_KEY, 'scene-alpha')

    const store = useProjectStore()
    expect(store.root_id).toBe('root-alpha')
    expect(store.branch_id).toBe('branch-alpha')
    expect((store as { scene_id?: string }).scene_id).toBe('scene-alpha')
  })

  it('projectStore sync setCurrentProject persists context to localStorage', async () => {
    const store = useProjectStore()
    const setCurrentProject = assertAction<
      (rootId: string, branchId: string, sceneId: string) => void | Promise<void>
    >(store.setCurrentProject, 'setCurrentProject')

    await setCurrentProject('root-7', 'branch-7', 'scene-7')

    expect(store.root_id).toBe('root-7')
    expect(store.branch_id).toBe('branch-7')
    expect((store as { scene_id?: string }).scene_id).toBe('scene-7')
    expect(localStorage.getItem(ROOT_ID_STORAGE_KEY)).toBe('root-7')
    expect(localStorage.getItem(BRANCH_ID_STORAGE_KEY)).toBe('branch-7')
    expect(localStorage.getItem(SCENE_ID_STORAGE_KEY)).toBe('scene-7')
  })

  it('projectStore sync updates context when route params change', async () => {
    const store = useProjectStore()
    const syncFromRoute = assertAction<(route: RouteContext) => void | Promise<void>>(
      store.syncFromRoute,
      'syncFromRoute',
    )

    await syncFromRoute(
      makeRoute({
        params: { sceneId: 'scene-alpha' },
        query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
      }),
    )

    expect(store.root_id).toBe('root-alpha')
    expect(store.branch_id).toBe('branch-alpha')
    expect((store as { scene_id?: string }).scene_id).toBe('scene-alpha')

    await syncFromRoute(
      makeRoute({
        params: { sceneId: 'scene-2' },
        query: { root_id: 'root-2', branch_id: 'branch-2' },
      }),
    )

    expect(store.root_id).toBe('root-2')
    expect(store.branch_id).toBe('branch-2')
    expect((store as { scene_id?: string }).scene_id).toBe('scene-2')
  })

  it('project context allows missing sceneId for editor/simulation routes', async () => {
    const store = useProjectStore()
    const syncFromRoute = assertAction<(route: RouteContext) => void | Promise<void>>(
      store.syncFromRoute,
      'syncFromRoute',
    )
    const setCurrentProject = assertAction<
      (rootId: string, branchId: string, sceneId: string) => void | Promise<void>
    >(store.setCurrentProject, 'setCurrentProject')

    await setCurrentProject('root-keep', 'branch-keep', 'scene-keep')

    await expect(
      syncFromRoute(
        makeRoute({
          name: 'editor',
          params: {},
          query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
        }),
      ),
    ).resolves.toBeUndefined()

    const sceneAfterEditor = (store as { scene_id?: string }).scene_id
    expect([undefined, '', 'scene-keep']).toContain(sceneAfterEditor)

    await expect(
      syncFromRoute(
        makeRoute({
          name: 'simulation',
          params: {},
          query: { root_id: 'root-2', branch_id: 'branch-2' },
        }),
      ),
    ).resolves.toBeUndefined()

    const sceneAfterSimulation = (store as { scene_id?: string }).scene_id
    expect([undefined, '', 'scene-keep']).toContain(sceneAfterSimulation)
  })
})

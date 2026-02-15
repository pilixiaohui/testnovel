import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
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
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
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

const readValue = (maybeRef: any) =>
  maybeRef && typeof maybeRef === 'object' && 'value' in maybeRef ? maybeRef.value : maybeRef

const getSetupState = (wrapper: any) => (wrapper.vm as any).$?.setupState ?? (wrapper.vm as any)

const getRunWorldAction = (wrapper: any) => {
  const setup = getSetupState(wrapper)
  return setup.runWorldAction as (action: () => Promise<void>, fallback: string) => Promise<void>
}

const getWorldActionError = (wrapper: any) => {
  const setup = getSetupState(wrapper)
  return readValue(setup.worldActionError)
}

const getWorldActionLoading = (wrapper: any) => {
  const setup = getSetupState(wrapper)
  return readValue(setup.worldActionLoading)
}

const mountWorldView = () => {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(WorldView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
    },
  })
}

describe('WorldView.runWorldAction edge cases', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params = { sceneId: '', rootId: '', branchId: '' }
    routeState.query = {}
    projectApiMock.fetchProjects.mockResolvedValue({ roots: [] })
    entityApiMock.fetchEntities.mockResolvedValue([])
    entityApiMock.fetchRelations.mockResolvedValue([])
    anchorApiMock.fetchAnchors.mockResolvedValue([])
    subplotApiMock.fetchSubplots.mockResolvedValue([])
  })

  it('success action: resolves and clears loading/error', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await runWorldAction(async () => {}, 'fallback')
    await flushPromises()

    expect(getWorldActionLoading(wrapper)).toBe(false)
    expect(getWorldActionError(wrapper)).toBe('')
  })

  it('non-required Error rejection: does not propagate and records message', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await expect(
      runWorldAction(async () => {
        throw new Error('network error')
      }, 'fallback'),
    ).resolves.toBeUndefined()
    await flushPromises()

    expect(getWorldActionLoading(wrapper)).toBe(false)
    expect(getWorldActionError(wrapper)).toBe('network error')
  })

  it('non-Error rejection: does not propagate and uses fallback (empty string)', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    const fallback = ''
    await expect(
      runWorldAction(async () => {
        throw 'bad' as any
      }, fallback),
    ).resolves.toBeUndefined()
    await flushPromises()

    expect(getWorldActionError(wrapper)).toBe(fallback)
  })

  it('undefined action: does not crash and records TypeError message', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await expect(runWorldAction(undefined as any, 'fallback')).resolves.toBeUndefined()
    await flushPromises()

    expect(String(getWorldActionError(wrapper))).toContain('not a function')
  })

  it('undefined fallback: does not crash and uses fallback as-is for non-Error rejection', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await expect(
      runWorldAction(async () => {
        throw { reason: 'bad' }
      }, undefined as any),
    ).resolves.toBeUndefined()
    await flushPromises()

    expect(getWorldActionError(wrapper)).toBeUndefined()
  })

  it('required field error: propagates (ends with "is required")', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await expect(
      runWorldAction(async () => {
        throw new Error('root_id is required')
      }, 'fallback'),
    ).rejects.toThrow('root_id is required')
    await flushPromises()

    expect(getWorldActionError(wrapper)).toBe('root_id is required')
  })

  it('required field error with whitespace: still propagates (trimmed)', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    await expect(
      runWorldAction(async () => {
        throw new Error('branch_id is required   ')
      }, 'fallback'),
    ).rejects.toThrow('branch_id is required')
    await flushPromises()

    expect(getWorldActionError(wrapper)).toBe('branch_id is required   ')
  })

  it('long/unicode fallback: uses fallback for non-Error rejection', async () => {
    const wrapper = mountWorldView()
    await flushPromises()

    const runWorldAction = getRunWorldAction(wrapper)
    const fallback = '加载失败-用户名🎉-' + 'a'.repeat(10_000)
    await expect(
      runWorldAction(async () => {
        throw { code: 500 }
      }, fallback),
    ).resolves.toBeUndefined()
    await flushPromises()

    expect(getWorldActionError(wrapper)).toBe(fallback)
  })

  it('consecutive calls: resolves without unhandled rejections and ends idle', async () => {
    const wrapper = mountWorldView()
    await flushPromises()
    expect(getWorldActionLoading(wrapper)).toBe(false)

    const runWorldAction = getRunWorldAction(wrapper)

    let resolveFirst!: () => void
    let resolveSecond!: () => void

    const first = runWorldAction(
      () =>
        new Promise<void>((resolve) => {
          resolveFirst = resolve
        }),
      'first',
    )

    const second = runWorldAction(
      () =>
        new Promise<void>((resolve) => {
          resolveSecond = resolve
        }),
      'second',
    )

    resolveFirst()
    resolveSecond()

    await expect(Promise.all([first, second])).resolves.toEqual([undefined, undefined])
    await flushPromises()

    expect(getWorldActionLoading(wrapper)).toBe(false)
  })
})

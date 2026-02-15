import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type {
  SnowflakeCharacter,
  SnowflakeSceneNode,
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakeStep5Payload,
  SnowflakeStructure,
} from '@/types/snowflake'
import { useSnowflakeStore } from '@/stores/snowflake'
import * as snowflakeApi from '@/api/snowflake'
import * as anchorApi from '@/api/anchor'

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  fetchSnowflakeRoot: vi.fn(),
  saveSnowflakeStep: vi.fn(),
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
  anchorApi: {
    generateAnchors: vi.fn(),
    listAnchors: vi.fn(),
    updateAnchor: vi.fn(),
    checkAnchor: vi.fn(),
  },
}))

const snowflakeApiMock = vi.mocked(snowflakeApi)
const anchorApiMock = vi.mocked(anchorApi)

const assertAction = <T extends (...args: any[]) => Promise<unknown>>(
  action: unknown,
  name: string,
): T => {
  if (typeof action !== 'function') {
    throw new Error(`Expected action \"${name}\" to be a function`)
  }
  return action as T
}

const createDeferred = <T>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const loadApiClient = async () => {
  const module = await import('@/api/index')
  return module.apiClient
}

describe('api client baseURL contract', () => {
  it('uses VITE_API_BASE_URL when set', async () => {
    const expected = import.meta.env.VITE_API_BASE_URL
    expect(typeof expected).toBe('string')
    expect(expected.length).toBeGreaterThan(0)
    const apiClient = await loadApiClient()
    expect(apiClient.defaults.baseURL).toBe(expected)
  })

  it('falls back to /api/v1 when VITE_API_BASE_URL is missing', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_API_BASE_URL', '')
    const apiClient = await loadApiClient()
    expect(apiClient.defaults.baseURL).toBe('/api/v1')
    vi.unstubAllEnvs()
  })
})

describe('snowflake store step contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('state exposes step1-6 fields', () => {
    const store = useSnowflakeStore()
    expect(store.$state).toHaveProperty('logline')
    expect(store.$state).toHaveProperty('root')
    expect(store.$state).toHaveProperty('characters')
    expect(store.$state).toHaveProperty('scenes')
    expect(store.$state).toHaveProperty('acts')
    expect(store.$state).toHaveProperty('chapters')
    expect(store.$state).toHaveProperty('anchors')

    expect(Array.isArray(store.characters)).toBe(true)
    expect(Array.isArray(store.scenes)).toBe(true)
    expect(Array.isArray(store.acts)).toBe(true)
    expect(Array.isArray(store.chapters)).toBe(true)
    expect(Array.isArray(store.anchors)).toBe(true)
  })

  it('actions call snowflake APIs and update state per step mapping', async () => {
    const store = useSnowflakeStore()
    expect(store.steps.logline).toEqual([])

    const loglines = ['one-sentence idea']
    const root: SnowflakeStructure = {
      logline: 'root-logline',
      three_disasters: ['d1', 'd2', 'd3'],
      ending: 'ending',
      theme: 'theme',
    }
    const characters: SnowflakeCharacter[] = [
      {
        entity_id: 'c1',
        name: 'Hero',
        ambition: 'goal',
        conflict: 'conflict',
        epiphany: 'epiphany',
        voice_dna: 'voice',
      },
    ]
    const scenes: SnowflakeSceneNode[] = [
      {
        id: 's1',
        branch_id: 'b1',
        parent_act_id: null,
        pov_character_id: 'c1',
        expected_outcome: 'win',
        conflict_type: 'internal',
        actual_outcome: 'lose',
        logic_exception: false,
        is_dirty: false,
      },
    ]
    const step4Result: SnowflakeStep4Result = {
      root_id: 'root-alpha',
      branch_id: 'branch-1',
      scenes,
    }
    const acts = [{ id: 'act-1' }]
    const chapters = [{ id: 'chapter-1' }]
    const anchors = ['anchor-1']

    snowflakeApiMock.fetchSnowflakeStep1.mockResolvedValue(loglines)
    snowflakeApiMock.fetchSnowflakeStep2.mockResolvedValue(root)
    snowflakeApiMock.fetchSnowflakeStep3.mockResolvedValue(characters)
    snowflakeApiMock.fetchSnowflakeStep4.mockResolvedValue(step4Result)
    snowflakeApiMock.fetchSnowflakeStep5.mockResolvedValue(acts)
    snowflakeApiMock.fetchSnowflakeStep6.mockResolvedValue(chapters)
    anchorApiMock.anchorApi.generateAnchors.mockResolvedValue(anchors)

    const fetchStep1 = assertAction<(idea: string) => Promise<void>>(store.fetchStep1, 'fetchStep1')
    await fetchStep1('idea')
    expect(snowflakeApiMock.fetchSnowflakeStep1).toHaveBeenCalledWith('idea')
    expect(store.logline).toEqual(loglines)

    const fetchStep2 = assertAction<(logline: string) => Promise<void>>(store.fetchStep2, 'fetchStep2')
    await fetchStep2(root.logline)
    expect(snowflakeApiMock.fetchSnowflakeStep2).toHaveBeenCalledWith(root.logline)
    expect(store.root).toEqual(root)

    const fetchStep3 = assertAction<(payload: SnowflakeStructure) => Promise<void>>(store.fetchStep3, 'fetchStep3')
    await fetchStep3(root)
    expect(snowflakeApiMock.fetchSnowflakeStep3).toHaveBeenCalledWith(root)
    expect(store.characters).toEqual(characters)

    const step4Payload: SnowflakeStep4Payload = {
      root,
      characters,
    }
    const fetchStep4 = assertAction<(payload: SnowflakeStep4Payload) => Promise<void>>(store.fetchStep4, 'fetchStep4')
    await fetchStep4(step4Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep4).toHaveBeenCalledWith(step4Payload)
    expect(store.scenes).toEqual(scenes)

    const step5Payload: SnowflakeStep5Payload = {
      root_id: step4Result.root_id,
      root,
      characters,
    }
    const fetchStep5 = assertAction<(payload: SnowflakeStep5Payload) => Promise<void>>(store.fetchStep5, 'fetchStep5')
    await fetchStep5(step5Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep5).toHaveBeenCalledWith(step5Payload)
    expect(snowflakeApiMock.fetchSnowflakeStep6).toHaveBeenCalledWith(step5Payload)
    expect(store.acts).toEqual(acts)
    expect(store.chapters).toEqual(chapters)

    const fetchStep6 = assertAction<() => Promise<void>>(store.fetchStep6, 'fetchStep6')
    await fetchStep6()
    expect(anchorApiMock.anchorApi.generateAnchors).toHaveBeenCalled()
    expect(store.anchors).toEqual(anchors)
  })

  it('does not advance state before async API resolves', async () => {
    const store = useSnowflakeStore()
    const deferred = createDeferred<SnowflakeCharacter[]>()

    snowflakeApiMock.fetchSnowflakeStep3.mockReturnValue(deferred.promise)

    const fetchStep3 = assertAction<(payload: SnowflakeStructure) => Promise<void>>(store.fetchStep3, 'fetchStep3')
    const root: SnowflakeStructure = {
      logline: 'root-logline',
      three_disasters: ['d1', 'd2', 'd3'],
      ending: 'ending',
      theme: 'theme',
    }

    const pending = fetchStep3(root)
    expect(store.characters).toEqual([])

    const characters: SnowflakeCharacter[] = [
      {
        entity_id: 'c1',
        name: 'Hero',
        ambition: 'goal',
        conflict: 'conflict',
        epiphany: 'epiphany',
        voice_dna: 'voice',
      },
    ]
    deferred.resolve(characters)
    await pending

    expect(store.characters).toEqual(characters)
  })
})

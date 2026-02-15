import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflakeStore } from '@/stores/snowflake'
import * as snowflakeApi from '@/api/snowflake'
import * as anchorApi from '@/api/anchor'
import * as branchApi from '@/api/branch'

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
}))

vi.mock('@/api/anchor', () => ({
  anchorApi: {
    generateAnchors: vi.fn(),
    listAnchors: vi.fn(),
    updateAnchor: vi.fn(),
    checkAnchor: vi.fn(),
  },
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    getRootSnapshot: vi.fn(),
  },
}))

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  fetchSnowflakeStep1: ReturnType<typeof vi.fn>
  fetchSnowflakeStep2: ReturnType<typeof vi.fn>
  fetchSnowflakeStep3: ReturnType<typeof vi.fn>
  saveSnowflakeStep: ReturnType<typeof vi.fn>
  snowflakeApi: {
    listActs: ReturnType<typeof vi.fn>
    listChapters: ReturnType<typeof vi.fn>
  }
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  anchorApi: {
    generateAnchors: ReturnType<typeof vi.fn>
    listAnchors: ReturnType<typeof vi.fn>
  }
}

const branchApiMock = vi.mocked(branchApi) as unknown as {
  branchApi: {
    getRootSnapshot: ReturnType<typeof vi.fn>
  }
}

const makeRootSnapshot = (overrides: Record<string, unknown> = {}) => ({
  root_id: 'root-alpha',
  branch_id: 'main',
  logline: '',
  theme: '',
  ending: '',
  characters: [],
  scenes: [],
  three_disasters: ['d1', 'd2', 'd3'],
  created_at: '2025-01-01T00:00:00Z',
  ...overrides,
})

describe('snowflake store branch coverage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    snowflakeApiMock.fetchSnowflakeStep1.mockResolvedValue(['logline'])
    snowflakeApiMock.fetchSnowflakeStep2.mockResolvedValue({ logline: 'root', theme: '', ending: '', three_disasters: ['d1', 'd2', 'd3'] })
    snowflakeApiMock.fetchSnowflakeStep3.mockResolvedValue([])
    snowflakeApiMock.saveSnowflakeStep.mockResolvedValue({ ok: true })
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([])
    snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue([])
    anchorApiMock.anchorApi.listAnchors.mockResolvedValue([])
    branchApiMock.branchApi.getRootSnapshot.mockResolvedValue(makeRootSnapshot())
  })

  it('throws when restoring without root id', async () => {
    const store = useSnowflakeStore()
    await expect(store.restoreFromBackend('')).rejects.toThrow('root_id is required')
  })

  it('throws when saving step without root id', async () => {
    const store = useSnowflakeStore()
    await expect(store.saveStepToBackend('step4', {})).rejects.toThrow('root_id is required')
  })

  it.each([
    {
      label: 'anchors',
      rootSnapshot: makeRootSnapshot(),
      anchors: [{ id: 'anchor-1' }],
      acts: [],
      chapters: [],
      expectedStep: 6,
    },
    {
      label: 'acts',
      rootSnapshot: makeRootSnapshot(),
      anchors: [],
      acts: [{ id: 'act-1' }],
      chapters: [{ id: 'chapter-1' }],
      expectedStep: 5,
    },
    {
      label: 'scenes',
      rootSnapshot: makeRootSnapshot({
        scenes: [
          {
            id: 'scene-alpha',
            title: 'Opening',
            sequence_index: 1,
            parent_act_id: 'act-1',
            is_skeleton: false,
          },
        ],
      }),
      anchors: [],
      acts: [],
      chapters: [],
      expectedStep: 4,
    },
    {
      label: 'characters',
      rootSnapshot: makeRootSnapshot({
        characters: [
          {
            name: 'Hero',
            ambition: 'Goal',
            conflict: 'Conflict',
            epiphany: 'Growth',
            voice_dna: 'Voice',
          },
        ],
      }),
      anchors: [],
      acts: [],
      chapters: [],
      expectedStep: 3,
    },
    {
      label: 'logline',
      rootSnapshot: makeRootSnapshot({ logline: 'Idea', theme: '', ending: '' }),
      anchors: [],
      acts: [],
      chapters: [],
      expectedStep: 2,
    },
    {
      label: 'empty',
      rootSnapshot: makeRootSnapshot(),
      anchors: [],
      acts: [],
      chapters: [],
      expectedStep: 1,
    },
  ])('restoreFromBackend selects step: $label', async ({ rootSnapshot, anchors, acts, chapters, expectedStep }) => {
    const store = useSnowflakeStore()

    branchApiMock.branchApi.getRootSnapshot.mockResolvedValue(rootSnapshot)
    snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue(acts)
    if (acts.length) {
      snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue(chapters)
    }
    anchorApiMock.anchorApi.listAnchors.mockResolvedValue(anchors)

    const result = await store.restoreFromBackend('root-alpha', 'main')

    expect(result.step).toBe(expectedStep)
  })

  it('fetches step1 with prompt options', async () => {
    const store = useSnowflakeStore()
    await store.fetchStep1('idea', { prompt: 'custom' })

    expect(snowflakeApiMock.fetchSnowflakeStep1).toHaveBeenCalledWith('idea', { prompt: 'custom' })
  })

  it('fetchStep6 throws when root or id missing', async () => {
    const store = useSnowflakeStore()

    await expect(store.fetchStep6()).rejects.toThrow('root_id is required')

    store.id = 'root-alpha'
    await expect(store.fetchStep6()).rejects.toThrow('root is required')
  })
})

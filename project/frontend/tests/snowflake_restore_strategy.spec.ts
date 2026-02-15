import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflakeStore } from '@/stores/snowflake'
import { apiClient } from '@/api/index'
import type { SnowflakeAct, SnowflakeAnchor, SnowflakeChapter } from '@/types/snowflake'

vi.mock('@/api/index', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    defaults: { baseURL: '/api/v1' },
  },
}))

const apiClientMock = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

const emptySteps = {
  logline: [],
  root: null,
  characters: [],
  scenes: [],
  acts: [],
  chapters: [],
  anchors: [],
}

const buildSnapshot = (rootId: string) => ({
  id: rootId,
  created_at: '2025-01-01T00:00:00Z',
  steps: { ...emptySteps },
})

type RootGraph = {
  root_id: string
  branch_id: string
  logline: string
  theme: string
  ending: string
  characters: unknown[]
  scenes: unknown[]
}

const setupApiMocks = (args: {
  rootId: string
  branchId: string
  rootGraph: RootGraph
  acts: SnowflakeAct[]
  chaptersByAct: Record<string, SnowflakeChapter[]>
  anchors: SnowflakeAnchor[]
}) => {
  const { rootId, branchId, rootGraph, acts, chaptersByAct, anchors } = args
  apiClientMock.get.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
    if (url === `/roots/${rootId}/snowflake/state`) {
      return Promise.resolve(buildSnapshot(rootId))
    }
    if (url === `/roots/${rootId}`) {
      expect(config?.params?.branch_id).toBe(branchId)
      return Promise.resolve(rootGraph)
    }
    if (url === `/roots/${rootId}/acts`) {
      return Promise.resolve(acts)
    }
    if (url === `/roots/${rootId}/anchors`) {
      expect(config?.params?.branch_id).toBe(branchId)
      return Promise.resolve(anchors)
    }
    if (url.startsWith('/acts/') && url.endsWith('/chapters')) {
      const actId = url.split('/')[2]
      return Promise.resolve(chaptersByAct[actId] ?? [])
    }
    return Promise.resolve(null)
  })
}

describe('snowflake restore strategy', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('restores from root graph + acts + chapters + anchors and avoids deprecated endpoints', async () => {
    const store = useSnowflakeStore()
    expect(store.steps.logline).toEqual([])
    const rootId = 'root-alpha'
    const branchId = 'main'

    const rootGraph: RootGraph = {
      root_id: rootId,
      branch_id: branchId,
      logline: 'logline',
      theme: 'theme',
      ending: 'ending',
      characters: [],
      scenes: [],
    }

    const acts: SnowflakeAct[] = [
      {
        id: 'act-1',
        root_id: rootId,
        sequence: 1,
        title: 'Act One',
        purpose: 'setup',
        tone: 'calm',
      },
    ]

    const chapters: SnowflakeChapter[] = [
      {
        id: 'chapter-1',
        act_id: acts[0].id,
        sequence: 1,
        title: 'Chapter One',
        focus: 'intro',
      },
    ]

    const anchors: SnowflakeAnchor[] = [{ id: 'anchor-1' }]

    setupApiMocks({
      rootId,
      branchId,
      rootGraph,
      acts,
      chaptersByAct: { [acts[0].id]: chapters },
      anchors,
    })

    await store.restoreFromBackend(rootId, branchId)

    const calledUrls = apiClientMock.get.mock.calls.map(([url]) => url)
    expect(calledUrls).not.toContain(`/roots/${rootId}/snowflake/state`)
    expect(calledUrls).not.toContain(`/roots/${rootId}/snowflake/steps`)
    expect(calledUrls).toContain(`/roots/${rootId}`)
    expect(calledUrls).toContain(`/roots/${rootId}/acts`)
    expect(calledUrls).toContain(`/acts/${acts[0].id}/chapters`)
    expect(calledUrls).toContain(`/roots/${rootId}/anchors`)
    expect(store.id).toBe(rootId)
    expect(store.steps.root).toMatchObject({
      logline: rootGraph.logline,
      theme: rootGraph.theme,
      ending: rootGraph.ending,
    })
    expect(store.steps.acts).toEqual(acts)
    expect(store.steps.chapters).toEqual(chapters)
    expect(store.steps.anchors).toEqual(anchors)
  })

  it.each([
    {
      name: 'step1 when no acts/chapters/anchors',
      acts: [] as SnowflakeAct[],
      chaptersByAct: {} as Record<string, SnowflakeChapter[]>,
      anchors: [] as SnowflakeAnchor[],
      expected: 1,
    },
    {
      name: 'step6 when anchors exist',
      acts: [
        {
          id: 'act-1',
          root_id: 'root-2',
          sequence: 1,
          title: 'Act One',
          purpose: 'setup',
          tone: 'calm',
        },
      ],
      chaptersByAct: {
        'act-1': [
          {
            id: 'chapter-1',
            act_id: 'act-1',
            sequence: 1,
            title: 'Chapter One',
            focus: 'intro',
          },
        ],
      },
      anchors: [{ id: 'anchor-1' }],
      expected: 6,
    },
  ])('infers step from recovered data: $name', async ({ acts, chaptersByAct, anchors, expected }) => {
    const store = useSnowflakeStore()
    const rootId = acts[0]?.root_id || 'root-alpha'
    const branchId = 'main'

    const rootGraph: RootGraph = {
      root_id: rootId,
      branch_id: branchId,
      logline: '',
      theme: '',
      ending: '',
      characters: [],
      scenes: [],
    }

    setupApiMocks({
      rootId,
      branchId,
      rootGraph,
      acts,
      chaptersByAct,
      anchors,
    })

    const result = await store.restoreFromBackend(rootId, branchId)
    const rawStep = (result as { step?: number | string } | undefined)?.step
    const normalizedStep =
      typeof rawStep === 'string' ? Number(rawStep.replace('step', '')) : rawStep

    expect(normalizedStep).toBe(expected)
  })

  it('fails fast when API call rejects', async () => {
    const store = useSnowflakeStore()
    const rootId = 'root-alpha'
    const branchId = 'main'

    apiClientMock.get.mockRejectedValue(new Error('network error'))

    await expect(store.restoreFromBackend(rootId, branchId)).rejects.toThrow('network error')
    expect(store.id).toBe('')
    expect(store.steps).toEqual(emptySteps)
  })
})

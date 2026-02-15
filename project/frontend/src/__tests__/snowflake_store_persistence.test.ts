import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflakeStore } from '../stores/snowflake'
import type { SnowflakeStructure } from '../types/snowflake'
import {
  fetchSnowflakeStep1,
  fetchSnowflakeStep2,
  fetchSnowflakeStep3,
  fetchSnowflakeStep4,
  fetchSnowflakeStep5,
  fetchSnowflakeStep6,
  saveSnowflakeStep,
} from '../api/snowflake'
import { anchorApi } from '../api/anchor'

vi.mock('../api/snowflake', () => ({
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

vi.mock('../api/anchor', () => ({
  anchorApi: {
    generateAnchors: vi.fn(),
  },
}))

vi.mock('../api/branch', () => ({
  branchApi: {
    getRootSnapshot: vi.fn(),
  },
}))

describe('snowflake store persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('persists snowflake steps once root id is available', async () => {
    const store = useSnowflakeStore()

    vi.mocked(fetchSnowflakeStep1).mockResolvedValue(['line-alpha'])
    vi.mocked(fetchSnowflakeStep2).mockResolvedValue({
      logline: 'line-alpha',
      theme: 'theme-alpha',
      ending: 'ending-alpha',
      three_disasters: ['d1', 'd2', 'd3'],
    })
    vi.mocked(fetchSnowflakeStep3).mockResolvedValue([
      {
        name: 'Hero',
        ambition: 'ambition',
        conflict: 'conflict',
        epiphany: 'epiphany',
        voice_dna: 'voice',
      },
    ])
    vi.mocked(fetchSnowflakeStep4).mockResolvedValue({
      root_id: 'root-alpha',
      branch_id: 'main',
      scenes: [],
    })
    vi.mocked(fetchSnowflakeStep5).mockResolvedValue([
      {
        id: 'act-alpha',
        root_id: 'root-alpha',
        sequence: 1,
        title: 'Act 1',
        purpose: 'Purpose',
        tone: 'calm',
      },
    ])
    vi.mocked(fetchSnowflakeStep6).mockResolvedValue([
      {
        id: 'chapter-alpha',
        act_id: 'act-alpha',
        sequence: 1,
        title: 'Chapter 1',
        focus: 'Focus',
      },
    ])
    vi.mocked(anchorApi.generateAnchors).mockResolvedValue([{ anchor: 'Anchor A' }])

    const loglines = await store.fetchStep1('idea-alpha')
    await store.fetchStep2(loglines[0])
    await store.fetchStep3(store.root as SnowflakeStructure)

    await store.fetchStep4({
      root: store.root as SnowflakeStructure,
      characters: store.characters,
    })

    await store.fetchStep5({
      root_id: store.id,
      root: store.root as SnowflakeStructure,
      characters: store.characters,
    })

    await store.fetchStep6('main')

    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step1',
      data: { logline: ['line-alpha'] },
    })
    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step2',
      data: { root: store.root },
    })
    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step3',
      data: { characters: store.characters },
    })
    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step4',
      data: {
        root: store.root,
        characters: store.characters,
        scenes: store.scenes,
      },
    })
    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step5',
      data: {
        acts: store.acts,
        chapters: store.chapters,
      },
    })
    expect(saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: 'root-alpha',
      step: 'step6',
      data: { anchors: store.anchors },
    })
  })
})

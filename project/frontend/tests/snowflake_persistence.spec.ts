import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type {
  SnowflakeAct,
  SnowflakeChapter,
  SnowflakeCharacter,
  SnowflakeRootState,
  SnowflakeSceneNode,
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakeStep5Payload,
  SnowflakeStructure,
} from '@/types/snowflake'
import { useSnowflakeStore } from '@/stores/snowflake'
import * as snowflakeApi from '@/api/snowflake'

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  fetchSnowflakeRoot: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  fetchSnowflakeState: vi.fn(),
}))

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  fetchSnowflakeStep4: ReturnType<typeof vi.fn>
  fetchSnowflakeStep5: ReturnType<typeof vi.fn>
  fetchSnowflakeStep6: ReturnType<typeof vi.fn>
  saveSnowflakeStep: ReturnType<typeof vi.fn>
  fetchSnowflakeState: ReturnType<typeof vi.fn>
}

const makeRoot = (): SnowflakeStructure => ({
  logline: 'root-logline',
  three_disasters: ['d1', 'd2', 'd3'],
  ending: 'ending',
  theme: 'theme',
})

const makeCharacters = (): SnowflakeCharacter[] => [
  {
    name: 'Hero',
    ambition: 'goal',
    conflict: 'conflict',
    epiphany: 'epiphany',
    voice_dna: 'voice',
  },
]

const makeScenes = (): SnowflakeSceneNode[] => [
  {
    id: 'scene-alpha',
    title: 'Opening',
    sequence_index: 1,
    parent_act_id: 'act-1',
    is_skeleton: false,
  },
]

const makeActs = (): SnowflakeAct[] => [
  {
    id: 'act-1',
    root_id: 'root-alpha',
    sequence: 1,
    title: 'Act One',
    purpose: 'setup',
    tone: 'calm',
  },
]

const makeChapters = (): SnowflakeChapter[] => [
  {
    id: 'chapter-1',
    act_id: 'act-1',
    sequence: 1,
    title: 'Chapter One',
    focus: 'intro',
  },
]

describe('M1-T4 snowflake persistence contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('test_snowflake_step_saves_to_backend', async () => {
    const store = useSnowflakeStore()

    const root = makeRoot()
    const characters = makeCharacters()
    const scenes = makeScenes()

    store.steps.root = root
    store.steps.characters = characters

    const step4Result: SnowflakeStep4Result = {
      root_id: 'root-alpha',
      branch_id: 'main',
      scenes,
    }

    snowflakeApiMock.fetchSnowflakeStep4.mockResolvedValue(step4Result)

    const payload: SnowflakeStep4Payload = {
      root,
      characters,
    }

    await store.fetchStep4(payload)

    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: step4Result.root_id,
      step: 'step4',
      data: {
        root,
        characters,
        scenes: step4Result.scenes,
      },
    })
  })


  it('test_snowflake_step_data_persisted', async () => {
    const store = useSnowflakeStore()

    const root = makeRoot()
    const characters = makeCharacters()
    const acts = makeActs()
    const chapters = makeChapters()

    store.id = 'root-alpha'
    store.steps.root = root
    store.steps.characters = characters

    snowflakeApiMock.fetchSnowflakeStep5.mockResolvedValue(acts)
    snowflakeApiMock.fetchSnowflakeStep6.mockResolvedValue(chapters)

    const payload: SnowflakeStep5Payload = {
      root_id: 'root-alpha',
      root,
      characters,
    }

    await store.fetchStep5(payload)

    expect(snowflakeApiMock.saveSnowflakeStep).toHaveBeenCalledWith({
      root_id: payload.root_id,
      step: 'step5',
      data: {
        acts,
        chapters,
      },
    })
  })
})
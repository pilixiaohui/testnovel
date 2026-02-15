import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflake } from '@/composables/useSnowflake'
import { useSnowflakeStore } from '@/stores/snowflake'

const makeRoot = () => ({
  logline: 'logline',
  theme: 'theme',
  ending: 'ending',
  three_disasters: ['d1', 'd2', 'd3'],
})

describe('useSnowflake composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('exposes reactive snapshots and reset', () => {
    const store = useSnowflakeStore()
    expect(store.steps.logline).toEqual([])
    const root = makeRoot()
    const character = {
      name: 'Hero',
      ambition: 'Goal',
      conflict: 'Conflict',
      epiphany: 'Growth',
      voice_dna: 'Voice',
    }
    const scene = {
      id: 'scene-alpha',
      title: 'Opening',
      sequence_index: 1,
      parent_act_id: 'act-1',
      is_skeleton: false,
    }
    const act = {
      id: 'act-1',
      root_id: 'root-alpha',
      sequence: 1,
      title: 'Act One',
      purpose: 'setup',
      tone: 'calm',
    }
    const chapter = {
      id: 'chapter-1',
      act_id: 'act-1',
      sequence: 1,
      title: 'Chapter One',
      focus: 'intro',
    }

    store.steps.logline = ['idea']
    store.steps.root = root
    store.steps.characters = [character]
    store.steps.scenes = [scene]
    store.steps.acts = [act]
    store.steps.chapters = [chapter]
    store.steps.anchors = [{ id: 'anchor-1' }]

    const snowflake = useSnowflake()

    expect(snowflake.store).toBe(store)
    expect(snowflake.logline.value).toEqual(['idea'])
    expect(snowflake.root.value).toEqual(root)
    expect(snowflake.characters.value).toEqual([character])
    expect(snowflake.scenes.value).toEqual([scene])
    expect(snowflake.acts.value).toEqual([act])
    expect(snowflake.chapters.value).toEqual([chapter])
    expect(snowflake.anchors.value).toEqual([{ id: 'anchor-1' }])

    snowflake.reset()

    expect(store.steps.logline).toEqual([])
    expect(store.steps.root).toBeNull()
    expect(store.steps.characters).toEqual([])
    expect(store.steps.scenes).toEqual([])
    expect(store.steps.acts).toEqual([])
    expect(store.steps.chapters).toEqual([])
    expect(store.steps.anchors).toEqual([])
  })
})

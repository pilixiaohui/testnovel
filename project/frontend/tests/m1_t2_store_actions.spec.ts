import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSnowflakeStore } from '@/stores/snowflake'
import { useEditorStore } from '@/stores/editor'
import { useProjectStore } from '@/stores/project'
import { useWorldStore } from '@/stores/world'
import * as sceneApi from '@/api/scene'
import * as entityApi from '@/api/entity'
import * as anchorApi from '@/api/anchor'
import * as subplotApi from '@/api/subplot'

vi.mock('@/api/scene', () => ({
  fetchSceneContext: vi.fn(),
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: vi.fn(),
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: vi.fn(),
}))

const sceneApiMock = vi.mocked(sceneApi) as unknown as {
  fetchSceneContext: ReturnType<typeof vi.fn>
}

const entityApiMock = vi.mocked(entityApi) as unknown as {
  fetchEntities: ReturnType<typeof vi.fn>
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  fetchAnchors: ReturnType<typeof vi.fn>
}

const subplotApiMock = vi.mocked(subplotApi) as unknown as {
  fetchSubplots: ReturnType<typeof vi.fn>
}

describe('M1-T2 store actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('updateStepContent updates snowflake steps based on content', () => {
    const store = useSnowflakeStore()

    store.updateStepContent(1, 'line-a\nline-b')
    expect(store.steps.logline).toEqual(['line-a', 'line-b'])

    const rootPayload = {
      id: 'root-alpha',
      logline: 'Root Logline',
      theme: 'Hope',
      ending: 'Victory',
      three_disasters: ['d1', 'd2', 'd3'],
    }
    store.updateStepContent(2, JSON.stringify(rootPayload))
    expect(store.steps.root).toEqual(rootPayload)
    expect(store.id).toBe('root-alpha')

    const charactersPayload = [
      {
        id: 'character-1',
        name: 'Hero',
        ambition: 'goal',
        conflict: 'conflict',
        epiphany: 'epiphany',
        voice_dna: 'voice',
      },
    ]
    store.updateStepContent(3, JSON.stringify(charactersPayload))
    expect(store.steps.characters).toEqual(charactersPayload)

    const scenesPayload = [
      {
        id: 'scene-alpha',
        title: 'Opening',
        sequence_index: 1,
        parent_act_id: 'act-1',
        is_skeleton: false,
      },
    ]
    store.updateStepContent(4, JSON.stringify(scenesPayload))
    expect(store.steps.scenes).toEqual(scenesPayload)

    const step5Payload = {
      acts: [
        {
          id: 'act-1',
          root_id: 'root-alpha',
          sequence: 1,
          title: 'Act I',
          purpose: 'setup',
          tone: 'calm',
        },
      ],
      chapters: [
        {
          id: 'chapter-1',
          act_id: 'act-1',
          sequence: 1,
          title: 'Chapter 1',
          focus: 'intro',
        },
      ],
    }
    store.updateStepContent(5, JSON.stringify(step5Payload))
    expect(store.steps.acts).toEqual(step5Payload.acts)
    expect(store.steps.chapters).toEqual(step5Payload.chapters)

    const anchorsPayload = ['anchor-alpha', 'anchor-beta']
    store.updateStepContent(6, JSON.stringify(anchorsPayload))
    expect(store.steps.anchors).toEqual(anchorsPayload)
  })

  it('selectScene loads scene context into editor store', async () => {
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

    sceneApiMock.fetchSceneContext.mockResolvedValue({
      id: 'scene-alpha',
      title: 'Scene Title',
      summary: 'Scene Summary',
      outcome: 'success',
      content: 'Scene Content',
    })

    const store = useEditorStore()
    await store.selectScene('scene-alpha')

    expect(sceneApiMock.fetchSceneContext).toHaveBeenCalledWith('scene-alpha', 'branch-alpha')
    expect(store.scene_id).toBe('scene-alpha')
    expect(store.title).toBe('Scene Title')
    expect(store.summary).toBe('Scene Summary')
    expect(store.outcome).toBe('success')
    expect(store.content).toBe('Scene Content')
    expect(store.is_dirty).toBe(false)
  })

  it('loadWorldData pulls entities/anchors/subplots and updates store', async () => {
    entityApiMock.fetchEntities.mockResolvedValue([
      {
        id: 'entity-1',
        created_at: '2025-01-01',
        name: 'Entity',
        type: 'character',
        position: { x: 0, y: 0, z: 0 },
      },
    ])
    anchorApiMock.fetchAnchors.mockResolvedValue([
      {
        id: 'anchor-1',
        anchor_type: 'inciting_incident',
        description: 'Opening',
      },
    ])
    subplotApiMock.fetchSubplots.mockResolvedValue(['subplot-1'])

    const store = useWorldStore()
    const result = await store.loadWorldData('root-alpha', 'main')

    expect(entityApiMock.fetchEntities).toHaveBeenCalledWith('root-alpha', 'main')
    expect(anchorApiMock.fetchAnchors).toHaveBeenCalledWith('root-alpha', 'main')
    expect(subplotApiMock.fetchSubplots).toHaveBeenCalledWith('root-alpha', 'main')
    expect(result.entities).toHaveLength(1)
    expect(result.anchors).toEqual(['Opening'])
    expect(result.subplots).toEqual(['subplot-1'])
    expect(store.entities).toEqual(result.entities)
    expect(store.anchors).toEqual(result.anchors)
  })
})

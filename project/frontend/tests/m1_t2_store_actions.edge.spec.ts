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

describe('M1-T2 store actions edge cases', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('updateStepContent(step, content)', () => {
    it.each([
      { step: 0 },
      { step: 7 },
      { step: -1 },
      { step: 1.2 },
      { step: Number.NaN },
      { step: Number.POSITIVE_INFINITY },
      { step: undefined },
      { step: null },
    ])('throws for invalid step: $step', ({ step }) => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(step as any, 'x')).toThrow()
    })

    it('step1 supports empty content', () => {
      const store = useSnowflakeStore()
      store.updateStepContent(1, '')
      expect(store.steps.logline).toEqual([''])
    })

    it('step1 supports unicode content', () => {
      const store = useSnowflakeStore()
      store.updateStepContent(1, '第一行\n第二行')
      expect(store.steps.logline).toEqual(['第一行', '第二行'])
    })

    it('step1 supports long content', () => {
      const store = useSnowflakeStore()
      const long = 'a'.repeat(10_000)
      store.updateStepContent(1, long)
      expect(store.steps.logline[0]).toHaveLength(10_000)
    })

    it('step2 throws on invalid JSON', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(2, 'not-json')).toThrow()
    })

    it('step2 throws on JSON null payload', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(2, 'null')).toThrow()
    })

    it('step3 throws when payload is not an array', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(3, JSON.stringify({}))).toThrow()
    })

    it('step4 throws when payload is not an array', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(4, JSON.stringify({}))).toThrow()
    })

    it('step5 throws when acts is not an array', () => {
      const store = useSnowflakeStore()
      const payload = {
        acts: {},
        chapters: [],
      }
      expect(() => store.updateStepContent(5, JSON.stringify(payload))).toThrow()
    })

    it('step5 throws when required fields are missing', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(5, JSON.stringify({}))).toThrow()
    })

    it('step6 throws when payload is not an array', () => {
      const store = useSnowflakeStore()
      expect(() => store.updateStepContent(6, JSON.stringify({}))).toThrow()
    })
  })

  describe('selectScene(sceneId)', () => {
    it.each([{ sceneId: '' }, { sceneId: undefined }, { sceneId: null }])(
      'throws for empty sceneId: $sceneId',
      async ({ sceneId }) => {
        const store = useEditorStore()
        await expect(store.selectScene(sceneId as any)).rejects.toThrow()
      },
    )
    it('throws when projectStore.branch_id is missing', async () => {
      const projectStore = useProjectStore()
      projectStore.branch_id = ''

      const store = useEditorStore()
      await expect(store.selectScene('scene-alpha')).rejects.toThrow()
      expect(sceneApiMock.fetchSceneContext).not.toHaveBeenCalled()
    })

    it('uses rendered_content when content is missing', async () => {
      const projectStore = useProjectStore()
      projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

      sceneApiMock.fetchSceneContext.mockResolvedValue({
        id: 'scene-alpha',
        title: 'T',
        summary: 'S',
        outcome: 'O',
        rendered_content: 'Rendered',
      })

      const store = useEditorStore()
      await store.selectScene('scene-alpha')
      expect(store.content).toBe('Rendered')
    })

    it('throws when both content and rendered_content are missing', async () => {
      const projectStore = useProjectStore()
      projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

      sceneApiMock.fetchSceneContext.mockResolvedValue({
        id: 'scene-alpha',
        title: 'T',
        summary: 'S',
        outcome: 'O',
      })

      const store = useEditorStore()
      await expect(store.selectScene('scene-alpha')).rejects.toThrow()
    })

    it('throws when required fields are missing', async () => {
      const projectStore = useProjectStore()
      projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

      sceneApiMock.fetchSceneContext.mockResolvedValue({
        id: 'scene-alpha',
        summary: 'S',
        outcome: 'O',
        content: 'C',
      })

      const store = useEditorStore()
      await expect(store.selectScene('scene-alpha')).rejects.toThrow()
    })

    it('accepts unicode/long sceneId', async () => {
      const projectStore = useProjectStore()
      projectStore.setCurrentProject('root-alpha', 'branch-alpha', '')

      const sceneId = `场景-${'a'.repeat(5_000)}`
      sceneApiMock.fetchSceneContext.mockResolvedValue({
        id: sceneId,
        title: 'Title',
        summary: 'Summary',
        outcome: 'Outcome',
        content: 'Content',
      })

      const store = useEditorStore()
      await store.selectScene(sceneId)

      expect(sceneApiMock.fetchSceneContext).toHaveBeenCalledWith(sceneId, 'branch-alpha')
      expect(store.scene_id).toBe(sceneId)
      expect(store.is_dirty).toBe(false)
    })
  })

  describe('loadWorldData(rootId, branchId)', () => {
    it('throws when rootId is empty', async () => {
      const store = useWorldStore()
      await expect(store.loadWorldData('', 'main')).rejects.toThrow()
    })

    it('throws when branchId is empty', async () => {
      const store = useWorldStore()
      await expect(store.loadWorldData('root-alpha', '')).rejects.toThrow()
    })

    it('throws when entities response is not an array', async () => {
      entityApiMock.fetchEntities.mockResolvedValue({} as any)
      anchorApiMock.fetchAnchors.mockResolvedValue([])
      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      await expect(store.loadWorldData('root-alpha', 'main')).rejects.toThrow()
      expect(store.entities).toEqual([])
      expect(store.anchors).toEqual([])
    })

    it('throws when anchors response is not an array', async () => {
      entityApiMock.fetchEntities.mockResolvedValue([])
      anchorApiMock.fetchAnchors.mockResolvedValue({} as any)
      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      await expect(store.loadWorldData('root-alpha', 'main')).rejects.toThrow()
      expect(store.entities).toEqual([])
      expect(store.anchors).toEqual([])
    })

    it('throws when anchor label cannot be derived', async () => {
      entityApiMock.fetchEntities.mockResolvedValue([])
      anchorApiMock.fetchAnchors.mockResolvedValue([{}])
      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      await expect(store.loadWorldData('root-alpha', 'main')).rejects.toThrow()
    })

    it('throws when subplots response is not an array', async () => {
      entityApiMock.fetchEntities.mockResolvedValue([])
      anchorApiMock.fetchAnchors.mockResolvedValue([])
      subplotApiMock.fetchSubplots.mockResolvedValue('subplot-1' as any)

      const store = useWorldStore()
      await expect(store.loadWorldData('root-alpha', 'main')).rejects.toThrow()
    })

    it('supports empty lists', async () => {
      entityApiMock.fetchEntities.mockResolvedValue([])
      anchorApiMock.fetchAnchors.mockResolvedValue([])
      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      const result = await store.loadWorldData('root-alpha', 'main')

      expect(result.entities).toEqual([])
      expect(result.anchors).toEqual([])
      expect(result.subplots).toEqual([])
      expect(store.entities).toEqual([])
      expect(store.anchors).toEqual([])
    })

    it('is safe to call repeatedly (last call wins)', async () => {
      expect(entityApiMock.fetchEntities).not.toHaveBeenCalled()
      entityApiMock.fetchEntities
        .mockResolvedValueOnce([
          {
            id: 'entity-1',
            created_at: '2025-01-01',
            name: 'Entity',
            type: 'character',
            position: { x: 0, y: 0, z: 0 },
          },
        ])
        .mockResolvedValueOnce([])

      anchorApiMock.fetchAnchors
        .mockResolvedValueOnce([
          {
            id: 'anchor-1',
            anchor_type: 'inciting_incident',
            description: 'First',
          },
        ])
        .mockResolvedValueOnce([
          {
            id: 'anchor-2',
            anchor_type: 'inciting_incident',
            description: 'Second',
          },
        ])

      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      await store.loadWorldData('root-alpha', 'main')
      await store.loadWorldData('root-beta', 'dev')

      expect(entityApiMock.fetchEntities).toHaveBeenNthCalledWith(1, 'root-alpha', 'main')
      expect(entityApiMock.fetchEntities).toHaveBeenNthCalledWith(2, 'root-beta', 'dev')
      expect(store.entities).toEqual([])
      expect(store.anchors).toEqual(['Second'])
    })

    it('accepts unicode ids', async () => {
      entityApiMock.fetchEntities.mockResolvedValue([])
      anchorApiMock.fetchAnchors.mockResolvedValue([])
      subplotApiMock.fetchSubplots.mockResolvedValue([])

      const store = useWorldStore()
      await store.loadWorldData('世界观-root', '主分支')

      expect(entityApiMock.fetchEntities).toHaveBeenCalledWith('世界观-root', '主分支')
      expect(anchorApiMock.fetchAnchors).toHaveBeenCalledWith('世界观-root', '主分支')
      expect(subplotApiMock.fetchSubplots).toHaveBeenCalledWith('世界观-root', '主分支')
    })
  })
})

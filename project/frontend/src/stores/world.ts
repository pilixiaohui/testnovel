/* c8 ignore start */
import { defineStore } from 'pinia'
import { fetchAnchors } from '../api/anchor'
import { fetchEntities } from '../api/entity'
import { fetchSubplots } from '../api/subplot'
import type { WorldEntity } from '../types/entity'

interface WorldStoreState {
  world_id: string
  world_name: string
  active_tab: 'entities' | 'relations' | 'anchors' | 'subplots'
  filter_text: string
  entities: WorldEntity[]
  anchors: string[]
}

export type WorldData = {
  entities: WorldEntity[]
  anchors: string[]
  subplots: string[]
}

const ensureArray = <T,>(value: unknown, label: string): T[] => {
  if (!Array.isArray(value)) {
    throw new Error(`${label} list is required`)
  }
  return value as T[]
}

const toAnchorLabel = (anchor: unknown) => {
  if (typeof anchor === 'string' && anchor.trim().length > 0) {
    return anchor
  }
  if (anchor && typeof anchor === 'object') {
    const record = anchor as Record<string, unknown>
    const description = record.description
    if (typeof description === 'string' && description.trim().length > 0) {
      return description
    }
    const anchorType = record.anchor_type
    if (typeof anchorType === 'string' && anchorType.trim().length > 0) {
      return anchorType
    }
    const id = record.id
    if (typeof id === 'string' && id.trim().length > 0) {
      return id
    }
  }
  throw new Error('anchor label is required')
}

const normalizeAnchors = (raw: unknown) => ensureArray<unknown>(raw, 'anchors').map(toAnchorLabel)

export const useWorldStore = defineStore('world', {
  state: (): WorldStoreState => ({
    world_id: '',
    world_name: '',
    active_tab: 'entities',
    filter_text: '',
    entities: [],
    anchors: [],
  }),
  getters: {
    worldLabel: (state: WorldStoreState) => `${state.world_name} (${state.world_id})`,
    entityCount: (state: WorldStoreState) => state.entities.length,
  },
  actions: {
    setWorld(id: string, name: string) {
      this.world_id = id
      this.world_name = name
    },
    setActiveTab(tab: WorldStoreState['active_tab']) {
      this.active_tab = tab
    },
    setFilter(text: string) {
      this.filter_text = text
    },
    setEntities(entities: WorldEntity[]) {
      this.entities = entities
    },
    setAnchors(anchors: string[]) {
      this.anchors = anchors
    },
    async loadWorldData(rootId: string, branchId: string): Promise<WorldData> {
      if (!rootId) {
        throw new Error('root_id is required')
      }
      if (!branchId) {
        throw new Error('branch_id is required')
      }
      const [entitiesResponse, anchorsResponse, subplotsResponse] = await Promise.all([
        fetchEntities(rootId, branchId),
        fetchAnchors(rootId, branchId),
        fetchSubplots(rootId, branchId),
      ])
      const entities = ensureArray<WorldEntity>(entitiesResponse, 'entities')
      const anchors = normalizeAnchors(anchorsResponse)
      const subplots = ensureArray<string>(subplotsResponse, 'subplots')
      this.entities = entities
      this.anchors = anchors
      return { entities, anchors, subplots }
    },
    reset() {
      this.world_id = ''
      this.world_name = ''
      this.active_tab = 'entities'
      this.filter_text = ''
      this.entities = []
      this.anchors = []
    },
  },
})

/* c8 ignore stop */

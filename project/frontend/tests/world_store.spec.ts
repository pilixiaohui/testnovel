import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorldStore } from '@/stores/world'
import type { WorldEntity } from '@/types/entity'

describe('world store behavior', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default state', () => {
    const store = useWorldStore()

    expect(store.world_id).toBe('')
    expect(store.world_name).toBe('')
    expect(store.active_tab).toBe('entities')
    expect(store.filter_text).toBe('')
    expect(store.entities).toEqual([])
    expect(store.anchors).toEqual([])
    expect(store.worldLabel).toBe(' ()')
    expect(store.entityCount).toBe(0)
  })

  it('updates world metadata and collections', () => {
    const store = useWorldStore()

    store.setWorld('world-1', 'Nova')
    store.setActiveTab('anchors')
    store.setFilter('hero')

    const entities: WorldEntity[] = [
      {
        id: 'e1',
        created_at: '2024-01-01',
        name: 'Hero',
        type: 'character',
        position: { x: 1, y: 2, z: 3 },
      },
      {
        id: 'e2',
        created_at: '2024-01-02',
        name: 'City',
        type: 'location',
        position: { x: 4, y: 5, z: 6 },
      },
    ]
    store.setEntities(entities)
    store.setAnchors(['Anchor A', 'Anchor B'])

    expect(store.world_id).toBe('world-1')
    expect(store.world_name).toBe('Nova')
    expect(store.active_tab).toBe('anchors')
    expect(store.filter_text).toBe('hero')
    expect(store.entities).toEqual(entities)
    expect(store.anchors).toEqual(['Anchor A', 'Anchor B'])
    expect(store.worldLabel).toBe('Nova (world-1)')
    expect(store.entityCount).toBe(2)
  })

  it('reset clears world state', () => {
    const store = useWorldStore()

    store.setWorld('world-2', 'Echo')
    store.setActiveTab('relations')
    store.setFilter('tag')
    store.setEntities([
      {
        id: 'e3',
        created_at: '2024-01-03',
        name: 'NPC',
        type: 'character',
        position: { x: 0, y: 0, z: 0 },
      },
    ])
    store.setAnchors(['Anchor C'])

    store.reset()

    expect(store.world_id).toBe('')
    expect(store.world_name).toBe('')
    expect(store.active_tab).toBe('entities')
    expect(store.filter_text).toBe('')
    expect(store.entities).toEqual([])
    expect(store.anchors).toEqual([])
  })
})

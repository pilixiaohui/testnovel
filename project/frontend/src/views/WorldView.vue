<template>
  <section class="page" data-test="world-manager-root">
    <header class="header">
      <div>
        <h1>World Manager</h1>
        <p class="subtitle">Manage worlds, entities, and anchor points.</p>
      </div>
      <div class="actions">
        <button type="button" data-test="world-create">Create World</button>
        <button type="button" data-test="world-load" @click="loadWorld">Load</button>
        <button type="button" data-test="world-entity-create" @click="createWorldEntity">Create Entity</button>
        <button type="button" data-test="world-entity-update" @click="updateWorldEntity">Update Entity</button>
        <button type="button" data-test="world-entity-delete" @click="deleteWorldEntity">Delete Entity</button>
        <button type="button" data-test="world-relations-show" @click="showRelationsGraph">
          Show Relations
        </button>
      </div>
    </header>

    <ApiFeedback :loading="apiLoading" :error="apiError" />

    <StateExtractPanel :root-id="rootId" :branch-id="branchId" @refresh="applyWorldRefresh" />

    <section class="panel">
      <h2>Worlds</h2>
      <div v-if="worldListError" class="empty-panel" data-test="world-error">
        <strong>Unable to load worlds.</strong>
        <p class="subtitle">Please retry after checking the project service.</p>
      </div>
      <div v-else-if="worldListEmpty" class="empty-panel" data-test="world-list-empty">
        <strong>No worlds yet.</strong>
        <p class="subtitle">Create a world to get started.</p>
      </div>
      <ul class="world-list" data-test="world-list">
        <li
          v-for="world in worlds"
          :key="world.id"
          class="world-item"
          data-test="world-list-item"
          :class="{ active: world.id === selectedWorldId }"
          @click="selectWorld(world)"
        >
          <div class="world-name">{{ world.name }}</div>
          <div class="world-meta">Root: {{ world.id }}</div>
        </li>
      </ul>
    </section>

    <section v-if="!hasSelectedWorld" class="panel empty-panel" data-test="world-detail-empty">
      <strong>Select a world.</strong>
      <p class="subtitle">Choose a world to load entities, anchors, and relations.</p>
    </section>

    <section v-else class="panel">
      <div class="world-summary">
        <div>
          <h2>{{ store.world_name }}</h2>
          <p class="subtitle">Root: {{ store.world_id }} · Branch: {{ branchId }}</p>
        </div>
      </div>
    </section>

    <section v-if="hasSelectedWorld" class="panel">
      <EntityList :entities="entities" />
    </section>

    <section v-if="hasSelectedWorld" class="panel">
      <AnchorTimeline :anchors="anchors" />
    </section>

    <section v-if="showRelations" class="panel" data-test="world-relations-graph">
      <RelationGraph :entities="relationEntities" :relations="relations" />
    </section>

    <section v-else-if="hasSelectedWorld" class="panel">
      <RelationGraph :entities="relationEntities" :relations="relations" />
    </section>

    <section v-if="hasSelectedWorld" class="panel">
      <h2>Subplots</h2>
      <ul v-if="subplots.length > 0" class="subplots-list">
        <li v-for="subplot in subplots" :key="subplot">{{ subplot }}</li>
      </ul>
      <div v-else class="empty-panel" data-test="subplot-empty">
        <strong>No subplots.</strong>
        <p class="subtitle">No subplots loaded for this world.</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { useWorldStore } from '../stores/world'
import StateExtractPanel from '../components/StateExtractPanel.vue'
import ApiFeedback from '../components/ApiFeedback.vue'
import EntityList from '../components/world/EntityList.vue'
import AnchorTimeline from '../components/world/AnchorTimeline.vue'
import RelationGraph from '../components/world/RelationGraph.vue'
import type { EntityRelationView, EntityView, WorldEntity } from '../types/entity'
import { fetchAnchors } from '../api/anchor'
import { fetchSubplots } from '../api/subplot'
import { createEntity, deleteEntity, fetchEntities, fetchRelations, updateEntity } from '../api/entity'

const route = useRoute()
const projectStore = useProjectStore()
const store = useWorldStore()

const resolveRouteString = (value: unknown) =>
  typeof value === 'string' && value.trim().length > 0 ? value : ''

const syncProjectContext = () => {
  if (projectStore.root_id && projectStore.branch_id) {
    return
  }
  void projectStore.syncFromRoute({
    name: typeof route.name === 'string' ? route.name : undefined,
    params: {
      sceneId: resolveRouteString(route.params.sceneId),
      rootId: resolveRouteString(route.params.rootId),
      branchId: resolveRouteString(route.params.branchId),
    },
    query: {
      root_id: resolveRouteString(route.query.root_id),
      branch_id: resolveRouteString(route.query.branch_id),
    },
  })
}

syncProjectContext()

const worldListLoading = ref(false)
const worldActionLoading = ref(false)
const worldActionError = ref('')
const relations = ref<EntityRelationView[]>([])
const subplots = ref<string[]>([])
const lastEntityId = ref('')
const showRelations = ref(false)

const worlds = computed(() =>
  projectStore.projects.map((project) => ({ id: project.root_id, name: project.name })),
)
const rootId = computed(() => projectStore.root_id)
const branchId = computed(() => projectStore.branch_id)
const worldListError = computed(() => projectStore.project_list_error)
const apiLoading = computed(() => worldListLoading.value || worldActionLoading.value)
const apiError = computed(() => worldActionError.value || worldListError.value || '')
const worldListEmpty = computed(
  () => !worldListLoading.value && !worldListError.value && worlds.value.length === 0,
)
const selectedWorldId = computed(() => store.world_id)
const hasSelectedWorld = computed(() => store.world_id.length > 0)
const entities = computed(() => store.entities)
const anchors = computed(() => store.anchors)

const relationEntities = computed<EntityView[]>(() => {
  const map = new Map<string, EntityView>()
  store.entities.forEach((entity) => {
    map.set(entity.id, {
      entity_id: entity.id,
      name: entity.name,
      entity_type: entity.type as EntityView['entity_type'],
      tags: [],
      arc_status: '',
      semantic_states: { position: entity.position },
    })
  })
  relations.value.forEach((relation) => {
    if (!map.has(relation.from_entity_id)) {
      map.set(relation.from_entity_id, {
        entity_id: relation.from_entity_id,
        name: relation.from_entity_id,
        tags: [],
        semantic_states: {},
      })
    }
    if (!map.has(relation.to_entity_id)) {
      map.set(relation.to_entity_id, {
        entity_id: relation.to_entity_id,
        name: relation.to_entity_id,
        tags: [],
        semantic_states: {},
      })
    }
  })
  return Array.from(map.values())
})

const requireRootId = () => {
  const value = rootId.value
  if (!value) {
    throw new Error('root_id is required')
  }
  return value
}

const requireBranchId = () => {
  const value = branchId.value
  if (!value) {
    throw new Error('branch_id is required')
  }
  return value
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

const normalizeRelations = (raw: unknown): EntityRelationView[] => {
  const list = ensureArray<unknown>(raw, 'relations')
  return list.map((item) => {
    if (!item || typeof item !== 'object') {
      throw new Error('relation item is required')
    }
    const record = item as Record<string, unknown>
    const from = record.from_entity_id
    const to = record.to_entity_id
    if (typeof from === 'string' && typeof to === 'string') {
      const relationType = typeof record.relation_type === 'string' ? record.relation_type : 'related'
      const tension = typeof record.tension === 'number' ? record.tension : 0
      return {
        from_entity_id: from,
        to_entity_id: to,
        relation_type: relationType,
        tension,
      }
    }
    const source = record.source
    const target = record.target
    if (typeof source === 'string' && typeof target === 'string') {
      return {
        from_entity_id: source,
        to_entity_id: target,
        relation_type: 'related',
        tension: 0,
      }
    }
    throw new Error('relation item is invalid')
  })
}

const applyWorldRefresh = (payload: { entities: WorldEntity[]; anchors: string[]; subplots: string[] }) => {
  store.setEntities(payload.entities)
  store.setAnchors(payload.anchors)
  subplots.value = payload.subplots
}

const shouldPropagateError = (error: unknown) =>
  error instanceof Error && error.message.trim().endsWith('is required')

const runWorldAction = async (action: () => Promise<void>, fallback: string) => {
  worldActionError.value = ''
  worldActionLoading.value = true
  try {
    await action()
  } catch (error) {
    worldActionError.value = error instanceof Error ? error.message : fallback
    if (shouldPropagateError(error)) {
      throw error
    }
  } finally {
    worldActionLoading.value = false
  }
}

const loadWorldList = async () => {
  worldListLoading.value = true
  try {
    await projectStore.listProjects()
  } catch (error) {
    worldActionError.value = error instanceof Error ? error.message : 'Failed to load worlds.'
  } finally {
    worldListLoading.value = false
  }
}

onMounted(() => {
  void loadWorldList()
})

type WorldOption = { id: string; name: string }

const loadWorldDetails = async (rootIdValue: string, branchIdValue: string) => {
  const [entityResponse, anchorResponse, subplotResponse] = await Promise.all([
    fetchEntities(rootIdValue, branchIdValue),
    fetchAnchors(rootIdValue, branchIdValue),
    fetchSubplots(rootIdValue, branchIdValue),
  ])
  store.setEntities(ensureArray<WorldEntity>(entityResponse, 'entities'))
  store.setAnchors(normalizeAnchors(anchorResponse))
  subplots.value = ensureArray<string>(subplotResponse, 'subplots')
}

const loadRelations = async (rootIdValue: string, branchIdValue: string) => {
  const relationResponse = await fetchRelations(rootIdValue, branchIdValue)
  relations.value = normalizeRelations(relationResponse)
}

const selectWorld = async (world: WorldOption) => {
  await runWorldAction(async () => {
    const branchIdValue = requireBranchId()
    showRelations.value = false
    store.setWorld(world.id, world.name)
    projectStore.setCurrentProject(world.id, branchIdValue, projectStore.scene_id)
    await loadWorldDetails(world.id, branchIdValue)
    await loadRelations(world.id, branchIdValue)
  }, 'Failed to load world.')
}

const loadWorld = async () => {
  await runWorldAction(async () => {
    const rootIdValue = requireRootId()
    const branchIdValue = requireBranchId()
    await loadWorldDetails(rootIdValue, branchIdValue)
  }, 'Failed to load world.')
}

const createWorldEntity = async () => {
  await runWorldAction(async () => {
    const rootIdValue = requireRootId()
    const branchIdValue = requireBranchId()
    const response = (await createEntity(rootIdValue, branchIdValue, {
      name: 'New Entity',
      entity_type: 'Character',
      tags: [],
      arc_status: 'active',
      semantic_states: {
        position: { x: 0, y: 0, z: 0 },
      },
    })) as { id?: string }
    const createdId = typeof response?.id === 'string' ? response.id : ''
    if (!createdId) {
      throw new Error('entity id is required')
    }
    lastEntityId.value = createdId
  }, 'Failed to create entity.')
}

const updateWorldEntity = async () => {
  await runWorldAction(async () => {
    const targetId = store.entities[0]?.id || lastEntityId.value
    if (!targetId) {
      throw new Error('entity id is required')
    }
    const rootIdValue = requireRootId()
    const branchIdValue = requireBranchId()
    await updateEntity(rootIdValue, branchIdValue, targetId, {
      name: 'Updated Entity',
      entity_type: 'Character',
      tags: ['updated'],
      arc_status: 'active',
      semantic_states: {
        position: { x: 1, y: 1, z: 1 },
      },
    })
  }, 'Failed to update entity.')
}

const deleteWorldEntity = async () => {
  await runWorldAction(async () => {
    const targetId = store.entities[0]?.id || lastEntityId.value
    if (!targetId) {
      throw new Error('entity id is required')
    }
    const rootIdValue = requireRootId()
    const branchIdValue = requireBranchId()
    await deleteEntity(rootIdValue, branchIdValue, targetId)
  }, 'Failed to delete entity.')
}

const showRelationsGraph = async () => {
  showRelations.value = false
  await runWorldAction(async () => {
    const rootIdValue = requireRootId()
    const branchIdValue = requireBranchId()
    await loadRelations(rootIdValue, branchIdValue)
    showRelations.value = true
  }, 'Failed to load relations.')
}
</script>

<style scoped>
.header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subtitle {
  margin: 4px 0 0;
  color: #6b7280;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 12px;
}

.world-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.world-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px 12px;
  display: grid;
  gap: 4px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.world-item.active {
  border-color: #6366f1;
  background: #eef2ff;
}

.world-name {
  font-weight: 600;
}

.world-meta {
  color: #6b7280;
  font-size: 12px;
}

.world-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subplots-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 6px;
}

.empty-panel {
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  padding: 12px;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}
</style>

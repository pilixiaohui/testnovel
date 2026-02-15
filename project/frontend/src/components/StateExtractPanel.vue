<template>
  <section class="panel" data-test="state-extract-panel">
    <header class="panel-header">
      <div>
        <h2>State Extract</h2>
        <p class="subtitle">Extract changes from the latest narrative context.</p>
      </div>
      <div class="actions">
        <button type="button" data-test="extract-state-btn" @click="extractState">提取状态</button>
        <button type="button" data-test="state-extract" @click="extractState">提取图信息</button>
        <button
          v-if="extractPreview"
          type="button"
          data-test="state-commit"
          @click="commitState"
        >
          提交变更
        </button>
      </div>
    </header>

    <section class="results" data-test="extract-results">
      <section v-if="extractError" class="message error" data-test="state-extract-error">
        <span>{{ extractError }}</span>
        <button type="button" data-test="state-extract-retry" @click="extractState">重试</button>
      </section>

      <pre v-if="extractPreview" class="output" data-test="state-extract-preview">{{ formattedPreview }}</pre>

      <section v-if="commitError" class="message error" data-test="state-commit-error">
        <span>{{ commitError }}</span>
        <button type="button" data-test="state-commit-retry" @click="commitState">重试</button>
      </section>

      <div v-if="commitStatus" class="message success" data-test="state-commit-status">
        {{ commitStatus }}
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { llmApi } from '../api/llm'
import { fetchAnchors } from '../api/anchor'
import { fetchEntities } from '../api/entity'
import { fetchSubplots } from '../api/subplot'
import type { WorldEntity } from '../types/entity'

type StateProposal = Record<string, unknown>

type ExtractPreview = StateProposal[]

type RefreshPayload = {
  entities: WorldEntity[]
  anchors: string[]
  subplots: string[]
}

const props = defineProps<{
  rootId: string
  branchId: string
  context?: Record<string, unknown>
}>()

const emit = defineEmits<{
  (event: 'refresh', payload: RefreshPayload): void
}>()

const extractPreview = ref<ExtractPreview | null>(null)
const extractError = ref('')
const commitError = ref('')
const commitStatus = ref('')

const formattedPreview = computed(() =>
  extractPreview.value ? JSON.stringify(extractPreview.value, null, 2) : '',
)

const readString = (value: unknown) =>
  typeof value === 'string' && value.trim().length > 0 ? value : ''

const readStringArray = (value: unknown) => {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item) => typeof item === 'string' && item.trim().length > 0)
}

const resolveContent = (context: Record<string, unknown>) =>
  readString(context.content) || readString(context.rendered_content) || readString(context.summary)

const resolveEntityIdsFromEntities = (value: unknown) => {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((entity) => {
      if (!entity || typeof entity !== 'object') {
        return ''
      }
      const record = entity as { entity_id?: unknown; id?: unknown }
      if (typeof record.entity_id === 'string') {
        return record.entity_id
      }
      return typeof record.id === 'string' ? record.id : ''
    })
    .filter((entityId) => entityId.trim().length > 0)
}

const resolveEntityIds = (context: Record<string, unknown>) => {
  const direct = readStringArray(context.entity_ids)
  if (direct.length > 0) {
    return direct
  }
  const fromSceneEntities = resolveEntityIdsFromEntities(context.scene_entities)
  if (fromSceneEntities.length > 0) {
    return fromSceneEntities
  }
  const fromCharacters = resolveEntityIdsFromEntities(context.characters)
  if (fromCharacters.length > 0) {
    return fromCharacters
  }
  const semanticStates = context.semantic_states
  if (semanticStates && typeof semanticStates === 'object' && !Array.isArray(semanticStates)) {
    return Object.keys(semanticStates).filter((entityId) => entityId.trim().length > 0)
  }
  return []
}

const buildExtractPayload = () => {
  const context = props.context ?? {}
  const content = resolveContent(context)
  const entityIds = resolveEntityIds(context)
  return {
    ...context,
    root_id: props.rootId,
    branch_id: props.branchId,
    content,
    entity_ids: entityIds,
  }
}

const resolveErrorMessage = (error: unknown, fallback: string) => {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }
  return fallback
}

const unwrapProposalList = (payload: unknown): ExtractPreview => {
  const resolved = (payload as { data?: unknown }).data ?? payload
  if (!Array.isArray(resolved)) {
    throw new Error('state proposals list is required')
  }
  return resolved as ExtractPreview
}

const extractState = async () => {
  extractError.value = ''
  commitError.value = ''
  commitStatus.value = ''
  extractPreview.value = null
  const payload = buildExtractPayload()
  if (!payload.root_id || !payload.branch_id) {
    extractError.value = 'root_id and branch_id are required for state extract.'
    return
  }
  if (!payload.content) {
    extractError.value = 'content is required for state extract.'
    return
  }
  try {
    if (!Array.isArray(payload.entity_ids) || payload.entity_ids.length === 0) {
      const fallbackEntities = await fetchEntities(payload.root_id, payload.branch_id)
      payload.entity_ids = resolveEntityIdsFromEntities(fallbackEntities)
    }
    if (!Array.isArray(payload.entity_ids) || payload.entity_ids.length === 0) {
      extractError.value = 'entity_ids are required for state extract.'
      return
    }
    const result = await llmApi.stateExtract(payload)
    extractPreview.value = unwrapProposalList(result)
  } catch (error) {
    extractError.value = resolveErrorMessage(error, 'Failed to extract state.')
  }
}

const commitState = async () => {
  commitError.value = ''
  commitStatus.value = ''
  if (!extractPreview.value) {
    return
  }
  try {
    if (!Array.isArray(extractPreview.value)) {
      throw new Error('state proposals list is required')
    }
    await llmApi.stateCommit(props.rootId, props.branchId, extractPreview.value)
    const [entities, anchors, subplots] = await Promise.all([
      fetchEntities(props.rootId, props.branchId),
      fetchAnchors(props.rootId, props.branchId),
      fetchSubplots(props.rootId, props.branchId),
    ])
    emit('refresh', {
      entities: entities as unknown as WorldEntity[],
      anchors: anchors as unknown as string[],
      subplots: subplots as unknown as string[],
    })
    commitStatus.value = 'World updated.'
  } catch (error) {
    commitError.value = resolveErrorMessage(error, 'Failed to commit state.')
  }
}
</script>

<style scoped>
.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 12px;
}

.panel-header {
  display: flex;
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
  gap: 8px;
  flex-wrap: wrap;
}

.output {
  margin: 0;
  background: #f9fafb;
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
}

.message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 8px;
}

.error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fca5a5;
}

.success {
  background: #ecfdf3;
  color: #047857;
  border: 1px solid #6ee7b7;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}
</style>

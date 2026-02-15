<template>
  <section class="page" data-test="scene-editor-root">
    <header class="header">
      <div>
        <h1>Scene Editor</h1>
        <p class="subtitle">Edit beats and context for the active scene.</p>
      </div>
      <div class="actions">
        <button type="button" data-test="scene-load" :disabled="!hasSceneId" @click="loadScene">Load</button>
        <button type="button" data-test="scene-save" :disabled="!hasSceneId || isSaving" @click="saveScene">Save</button>
        <button type="button" data-test="scene-diff" :disabled="!hasSceneId" @click="diffSceneView">Diff</button>
        <button type="button" data-test="scene-render" :disabled="!hasSceneId" @click="renderSceneView">Render</button>
        <span v-if="isDirty" class="dirty" data-test="scene-dirty">Dirty</span>
        <span v-if="isSaving" class="saving" data-test="scene-saving">Saving...</span>
      </div>
    </header>

    <div v-if="apiError" data-test="scene-error">
      <ApiFeedback :loading="apiLoading" :error="apiError" />
    </div>
    <ApiFeedback v-else :loading="apiLoading" :error="apiError" />

    <section v-if="!hasSceneId" class="panel empty-panel" data-test="scene-empty">
      <strong>Scene required.</strong>
      <p class="subtitle">Select a scene before editing.</p>
    </section>

    <section class="panel" data-test="scene-selector">
      <h2>Scenes</h2>
      <div v-if="!hasProjectContext" class="empty-panel" data-test="scene-list-context-missing">
        <strong>Project context required.</strong>
        <p class="subtitle">Select a project and branch to load scenes.</p>
      </div>
      <div v-else-if="sceneListError" class="empty-panel" data-test="scene-list-error">
        <strong>Unable to load scenes.</strong>
        <p class="subtitle">{{ sceneListError }}</p>
      </div>
      <div v-else-if="sceneOptions.length === 0" class="empty-panel" data-test="scene-list-empty">
        <strong>No scenes yet.</strong>
        <p class="subtitle">Generate scenes in Snowflake step 4 first.</p>
      </div>
      <div v-else class="scene-select">
        <label class="field">
          <span class="label">Select Scene</span>
          <select
            v-model="selectedSceneId"
            data-test="scene-select"
            :disabled="sceneListLoading"
            @change="applySceneSelection"
          >
            <option v-for="scene in sceneOptions" :key="scene.id" :value="scene.id">
              {{ scene.label }}
            </option>
          </select>
        </label>
      </div>
    </section>

    <StateExtractPanel
      :root-id="worldRootId"
      :branch-id="worldBranchId"
      :context="stateExtractContext"
    />


    <section class="panel" data-test="scene-editor-form">
      <label class="field">
        <span class="label">Title</span>
        <input
          v-model="title"
          data-test="scene-title-input"
          type="text"
          :disabled="!hasSceneId"
          readonly
        />
      </label>

      <label class="field">
        <span class="label">Summary</span>
        <textarea
          v-model="summary"
          data-test="scene-summary-input"
          rows="4"
          placeholder="Scene summary"
          :disabled="!hasSceneId"
          @input="handleSummaryChange"
        ></textarea>
      </label>

      <label class="field">
        <span class="label">Outcome</span>
        <select v-model="outcome" data-test="scene-outcome-select" :disabled="!hasSceneId" @change="handleOutcomeChange">
          <option value="success">Success</option>
          <option value="partial">Partial</option>
          <option value="failure">Failure</option>
        </select>
      </label>

      <label class="field">
        <span class="label">Content</span>
        <textarea
          v-model="content"
          data-test="scene-content-input"
          rows="10"
          placeholder="Scene content"
          :disabled="!hasSceneId"
          @input="handleContentChange"
        ></textarea>
      </label>

      <label class="field">
        <span class="label">Notes</span>
        <textarea
          v-model="notes"
          rows="3"
          placeholder="Notes"
          :disabled="!hasSceneId"
          readonly
        ></textarea>
      </label>
    </section>


    <section class="panel">
      <h2>Diff</h2>
      <pre class="output" data-test="scene-diff-output">{{ diffContent }}</pre>
    </section>

    <section class="panel">
      <h2>Render</h2>
      <pre class="output" data-test="scene-render-output">{{ renderedContent }}</pre>
    </section>

    <section class="panel" data-test="version-control-root">
      <h2>Version Control</h2>
      <div class="version-control-grid">
        <div class="version-control-card">
          <h3>Branches</h3>
          <p class="version-control-current" data-test="branch-current">Current: {{ currentBranch }}</p>
          <ul class="version-control-list" data-test="branch-list">
            <li v-for="branch in branches" :key="branch">{{ branch }}</li>
          </ul>
          <div class="version-control-actions">
            <select v-model="selectedBranch" data-test="branch-switch-select">
              <option v-for="branch in branches" :key="branch" :value="branch">{{ branch }}</option>
            </select>
            <button type="button" data-test="branch-switch" @click="switchBranch">Switch</button>
          </div>
        </div>
        <div class="version-control-card">
          <h3>Commit History</h3>
          <button type="button" data-test="commit-history-load" @click="loadCommitHistory">Load History</button>
          <ul class="version-control-list" data-test="commit-history-list">
            <li v-for="commit in commitHistory" :key="commit.id">{{ commit.id }} · {{ commit.message }}</li>
          </ul>
        </div>
        <div class="version-control-card">
          <h3>Snapshot</h3>
          <div class="version-control-actions">
            <button type="button" data-test="snapshot-load" @click="loadSnapshot">Load Snapshot</button>
            <button type="button" data-test="snapshot-restore" @click="restoreSnapshot">Restore Snapshot</button>
          </div>
          <pre class="output" data-test="snapshot-output">{{ snapshotOutput }}</pre>
          <div v-if="snapshotRestoreStatus" class="snapshot-status" data-test="snapshot-restore-status">
            {{ snapshotRestoreStatus }}
          </div>
        </div>
      </div>
    </section>

    <section class="panel" data-test="chapter-review-panel">
      <h2>Chapter Review</h2>
      <div v-if="chapters.length === 0" class="empty" data-test="chapter-review-empty">
        暂无章节
      </div>
      <div v-else class="chapter-review-list">
        <div
          v-for="chapter in chapters"
          :key="chapter.id"
          class="chapter-review-item"
          data-test="chapter-review-item"
        >
          <div class="chapter-review-meta">
            <span class="chapter-review-title">第 {{ chapter.sequence }} 章 · {{ chapter.title }}</span>
            <el-tag
              :type="reviewStatusTagType(chapter.review_status)"
              size="small"
              data-test="chapter-review-status"
            >
              {{ reviewStatusLabel(chapter.review_status) }}
            </el-tag>
          </div>
          <div class="chapter-review-actions">
            <div class="chapter-render-actions" data-test="chapter-render-btn">
              <el-button
                size="small"
                data-test="chapter-render"
                @click="renderChapterContent(chapter.id)"
              >
                Render
              </el-button>
            </div>
            <el-button
              size="small"
              type="success"
              data-test="chapter-approve"
              @click="submitChapterReview(chapter.id, 'approved')"
            >
              Approve
            </el-button>
            <el-button
              size="small"
              type="danger"
              data-test="chapter-reject"
              @click="submitChapterReview(chapter.id, 'rejected')"
            >
              Reject
            </el-button>
          </div>
          <div
            v-if="chapterRenderError[chapter.id]"
            class="chapter-render-error"
            data-test="chapter-render-error"
          >
            <span>{{ chapterRenderError[chapter.id] }}</span>
            <el-button size="small" data-test="chapter-render-retry" @click="renderChapterContent(chapter.id)">
              Retry
            </el-button>
          </div>
          <pre v-if="chapterRenderOutput[chapter.id]" class="output" data-test="chapter-render-output">
            {{ chapterRenderOutput[chapter.id] }}
          </pre>
          <pre v-if="chapterRenderQualityText(chapter.id)" class="output" data-test="chapter-render-quality">
            {{ chapterRenderQualityText(chapter.id) }}
          </pre>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEditorStore } from '../stores/editor'
import { useProjectStore } from '../stores/project'
import { useSnowflake } from '../composables/useSnowflake'
import { snowflakeApi } from '../api/snowflake'
import StateExtractPanel from '../components/StateExtractPanel.vue'
import ApiFeedback from '../components/ApiFeedback.vue'
import { renderChapter, reviewChapter } from '../api/chapter'
import { branchApi } from '../api/branch'
import { diffScene, fetchSceneContext, fetchScenes, renderScene, updateScene } from '../api/scene'
import type { ChapterReviewAction, ChapterReviewStatus } from '../types/snowflake'

const store = useEditorStore()
const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()
const { store: snowflakeStore, chapters } = useSnowflake()

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

const requireProjectRootId = () => {
  const value = projectStore.root_id
  if (!value) {
    throw new Error('root_id is required')
  }
  return value
}

const requireProjectBranchId = () => {
  const value = projectStore.branch_id
  if (!value) {
    throw new Error('branch_id is required')
  }
  return value
}

const resolveSceneId = () => {
  const fromRoute = resolveRouteString(route.params.sceneId)
  if (fromRoute) {
    return fromRoute
  }
  if (store.scene_id) {
    return store.scene_id
  }
  return ''
}

const worldRootId = computed(() => projectStore.root_id)
const worldBranchId = computed(() => projectStore.branch_id)
const sceneContext = ref<Record<string, unknown> | null>(null)
const sceneListLoading = ref(false)
const sceneListError = ref('')
const sceneOptions = ref<{ id: string; label: string }[]>([])
const selectedSceneId = ref('')
const hasProjectContext = computed(() => Boolean(projectStore.root_id && projectStore.branch_id))

const pickNonEmpty = (...values: Array<string | undefined | null>) => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim().length > 0) {
      return value
    }
  }
  return ''
}

const readString = (context: Record<string, unknown> | null, key: string) => {
  if (!context) {
    return undefined
  }
  const value = context[key]
  if (typeof value === 'string' && value.trim().length > 0) {
    return value
  }
  return undefined
}

const unwrapData = (raw: unknown) => {
  const normalized = typeof raw === 'string' ? (JSON.parse(raw) as unknown) : raw
  return (normalized as { data?: unknown }).data ?? normalized
}

const normalizeSceneOptions = (payload: unknown) => {
  const normalized = typeof payload === 'string' ? (JSON.parse(payload) as unknown) : payload
  const root = (normalized as { data?: unknown }).data ?? normalized
  if (!root || typeof root !== 'object') {
    throw new Error('scene payload is required')
  }
  const scenes = (root as { scenes?: unknown }).scenes
  if (!Array.isArray(scenes)) {
    throw new Error('scenes list is required')
  }
  return scenes.map((scene) => {
    if (!scene || typeof scene !== 'object') {
      throw new Error('scene item is required')
    }
    const record = scene as Record<string, unknown>
    const id = typeof record.id === 'string' ? record.id : ''
    if (!id) {
      throw new Error('scene id is required')
    }
    return { id, label: id }
  })
}

const loadSceneOptions = async () => {
  sceneListLoading.value = true
  sceneListError.value = ''
  try {
    const rootIdValue = requireProjectRootId()
    const branchIdValue = requireProjectBranchId()
    const payload = await fetchScenes(rootIdValue, branchIdValue)
    sceneOptions.value = normalizeSceneOptions(payload)
    if (sceneId.value && !selectedSceneId.value) {
      selectedSceneId.value = sceneId.value
    }
  } catch (error) {
    sceneOptions.value = []
    sceneListError.value = error instanceof Error ? error.message : 'Failed to load scenes.'
  } finally {
    sceneListLoading.value = false
  }
}

const applySceneSelection = async () => {
  const nextSceneId = selectedSceneId.value
  if (!nextSceneId) {
    throw new Error('scene_id is required')
  }
  const rootIdValue = requireProjectRootId()
  const branchIdValue = requireProjectBranchId()
  projectStore.setCurrentProject(rootIdValue, branchIdValue, nextSceneId)
  await router.push({
    name: 'editor',
    params: { sceneId: nextSceneId },
    query: { root_id: rootIdValue, branch_id: branchIdValue },
  })
}

const buildRenderPayload = (context: Record<string, unknown> | null) => {
  const voiceDna = pickNonEmpty(readString(context, 'voice_dna'), store.notes, 'neutral')
  const conflictType = pickNonEmpty(readString(context, 'conflict_type'), 'internal')
  const outlineRequirement = pickNonEmpty(
    readString(context, 'outline_requirement'),
    readString(context, 'summary'),
    store.summary,
    store.title,
    'scene outline',
  )
  const userIntent = pickNonEmpty(readString(context, 'user_intent'), store.outcome, 'render scene')
  const expectedOutcome = pickNonEmpty(
    readString(context, 'expected_outcome'),
    store.summary,
    store.title,
    'resolve conflict',
  )
  const worldState = (() => {
    const candidate = context?.world_state
    if (candidate && typeof candidate === 'object' && !Array.isArray(candidate)) {
      return candidate as Record<string, unknown>
    }
    const semanticStates = context?.semantic_states
    if (semanticStates && typeof semanticStates === 'object' && !Array.isArray(semanticStates)) {
      return semanticStates as Record<string, unknown>
    }
    return {}
  })()
  return {
    voice_dna: voiceDna,
    conflict_type: conflictType,
    outline_requirement: outlineRequirement,
    user_intent: userIntent,
    expected_outcome: expectedOutcome,
    world_state: worldState,
  }
}
const sceneId = computed(() => resolveSceneId())
const hasSceneId = computed(() => sceneId.value.length > 0)
const branchId = computed(() => worldBranchId.value)
const fromCommitId = ref('')
const toCommitId = ref('')
const diffContent = ref('')
const renderedContent = ref('')
const errorMessage = ref('')
const chapterRenderOutput = ref<Record<string, string>>({})
const chapterRenderQuality = ref<Record<string, Record<string, number>>>({})
const chapterRenderError = ref<Record<string, string>>({})

type CommitHistoryItem = {
  id: string
  parent_id?: string | null
  message?: string
  created_at?: string
}

const branches = ref<string[]>([])
const currentBranch = ref('main')
const selectedBranch = ref('main')
const commitHistory = ref<CommitHistoryItem[]>([])
const snapshotOutput = ref('')
const snapshotRestoreStatus = ref('')

const title = ref(store.title)
const summary = ref(store.summary)
const outcome = ref(store.outcome)
const notes = ref(store.notes)
const content = ref(store.content)

const stateExtractContext = computed(() => ({
  scene_id: sceneId.value,
  content: content.value,
  summary: summary.value,
  scene_entities: sceneContext.value?.scene_entities,
}))

const isDirty = computed(() => store.is_dirty)
const isSaving = computed(() => store.is_saving)

const apiLoading = computed(() => sceneListLoading.value || isSaving.value)
const apiError = computed(() => errorMessage.value)

const normalizeReviewStatus = (status?: ChapterReviewStatus): ChapterReviewStatus =>
  status ?? 'pending'

const reviewStatusLabel = (status?: ChapterReviewStatus) => normalizeReviewStatus(status)

const reviewStatusTagType = (status?: ChapterReviewStatus) => {
  const normalized = normalizeReviewStatus(status)
  if (normalized === 'approved') {
    return 'success'
  }
  if (normalized === 'rejected') {
    return 'danger'
  }
  return 'info'
}

const updateChapterReviewStatus = (chapterId: string, status: ChapterReviewStatus) => {
  const target = snowflakeStore.steps.chapters.find((chapter) => chapter.id === chapterId)
  if (target) {
    target.review_status = status
  }
}

const submitChapterReview = async (chapterId: string, status: ChapterReviewAction) => {
  try {
    errorMessage.value = ''
    const response = (await reviewChapter(chapterId, status)) as {
      review_status?: ChapterReviewStatus
    }
    if (!response.review_status) {
      throw new Error('review_status is required')
    }
    updateChapterReviewStatus(chapterId, response.review_status)
  } catch (error) {
    errorMessage.value = 'Failed to review chapter.'
  }
}

const chapterRenderQualityText = (chapterId: string) => {
  const scores = chapterRenderQuality.value[chapterId]
  if (!scores || Object.keys(scores).length === 0) {
    return ''
  }
  return JSON.stringify(scores, null, 2)
}

const renderChapterContent = async (chapterId: string) => {
  chapterRenderError.value[chapterId] = ''
  try {
    const response = (await renderChapter(chapterId)) as {
      rendered_content?: string
      quality_scores?: Record<string, number>
    }
    chapterRenderOutput.value[chapterId] = response.rendered_content ?? ''
    chapterRenderQuality.value[chapterId] = response.quality_scores ?? {}
  } catch (error) {
    chapterRenderError.value[chapterId] = 'Failed to render chapter.'
    chapterRenderOutput.value[chapterId] = ''
    chapterRenderQuality.value[chapterId] = {}
  }
}

const loadChapters = async () => {
  try {
    errorMessage.value = ''
    const acts = await snowflakeApi.listActs(worldRootId.value)
    if (!Array.isArray(acts)) {
      throw new Error('acts list is required')
    }
    snowflakeStore.steps.acts = acts
    const chapterLists = (await Promise.all(
      acts.map((act) => snowflakeApi.listChapters(act.id)),
    )) as unknown as Array<typeof snowflakeStore.steps.chapters>
    const merged = chapterLists.flat().filter(Boolean)
    snowflakeStore.steps.chapters = merged
  } catch (error) {
    errorMessage.value = 'Failed to load chapters.'
  }
}

const normalizeCommitHistory = (history: unknown): CommitHistoryItem[] => {
  const list = Array.isArray(history)
    ? history
    : history &&
        typeof history === 'object' &&
        Array.isArray((history as { data?: unknown }).data)
      ? (history as { data: unknown[] }).data
      : []
  return list
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null
      }
      const record = item as Record<string, unknown>
      const id = typeof record.id === 'string' ? record.id : ''
      if (!id) {
        return null
      }
      return {
        id,
        parent_id:
          typeof record.parent_id === 'string' || record.parent_id === null ? record.parent_id : undefined,
        message: typeof record.message === 'string' ? record.message : '',
        created_at: typeof record.created_at === 'string' ? record.created_at : undefined,
      }
    })
    .filter(Boolean) as CommitHistoryItem[]
}

const syncDiffRange = (history: CommitHistoryItem[]) => {
  if (history.length < 2) {
    fromCommitId.value = ''
    toCommitId.value = ''
    return
  }
  const [latest, previous] = history
  if (!latest || !previous) {
    throw new Error('commit history is required')
  }
  toCommitId.value = latest.id
  fromCommitId.value = previous.id
}

const loadBranches = async () => {
  try {
    errorMessage.value = ''
    const list = await branchApi.listBranches(worldRootId.value)
    if (!Array.isArray(list)) {
      throw new Error('branches list is required')
    }
    branches.value = list
    if (list.length > 0) {
      const first = list[0]
      if (!first) {
        throw new Error('branches list is required')
      }
      if (!list.includes(currentBranch.value)) {
        currentBranch.value = first
      }
      if (!list.includes(selectedBranch.value)) {
        selectedBranch.value = currentBranch.value
      }
    }
  } catch (error) {
    errorMessage.value = 'Failed to load branches.'
  }
}

const switchBranch = async () => {
  try {
    errorMessage.value = ''
    const response = (await branchApi.switchBranch(worldRootId.value, selectedBranch.value)) as {
      branch_id?: string
    }
    currentBranch.value = response.branch_id ?? selectedBranch.value
  } catch (error) {
    errorMessage.value = 'Failed to switch branch.'
  }
}

const loadCommitHistory = async () => {
  try {
    errorMessage.value = ''
    const history = await branchApi.getBranchHistory(worldRootId.value, currentBranch.value)
    const normalized = normalizeCommitHistory(history)
    commitHistory.value = normalized
    syncDiffRange(normalized)
  } catch (error) {
    errorMessage.value = 'Failed to load commit history.'
  }
}

const loadSnapshot = async () => {
  try {
    errorMessage.value = ''
    const snapshot = await branchApi.getRootSnapshot(worldRootId.value, currentBranch.value)
    snapshotOutput.value = JSON.stringify(snapshot, null, 2)
  } catch (error) {
    errorMessage.value = 'Failed to load snapshot.'
  }
}

const restoreSnapshot = async () => {
  try {
    errorMessage.value = ''
    snapshotRestoreStatus.value = ''
    const targetCommitId = commitHistory.value[0]?.id
    if (!targetCommitId) {
      throw new Error('commit history is required')
    }
    await branchApi.resetBranch(worldRootId.value, currentBranch.value, targetCommitId)
    snapshotRestoreStatus.value = 'Snapshot restored.'
  } catch (error) {
    errorMessage.value = 'Failed to restore snapshot.'
  }
}

onMounted(() => {
  if (!hasProjectContext.value) {
    return
  }

  void loadBranches()
  void loadChapters()
  void loadSceneOptions()
})

watch(sceneId, (value) => {
  if (value && value !== selectedSceneId.value) {
    selectedSceneId.value = value
  }
})

const handleSummaryChange = () => {
  store.updateSummary(summary.value)
  if (content.value !== summary.value) {
    content.value = summary.value
    store.updateContent(content.value)
  }
}

const handleContentChange = () => {
  store.updateContent(content.value)
  if (summary.value !== content.value) {
    summary.value = content.value
    store.updateSummary(summary.value)
  }
}

/* c8 ignore next */
const handleOutcomeChange = () => {
  store.updateOutcome(outcome.value)
}

const loadScene = async () => {
  if (!hasSceneId.value) {
    errorMessage.value = 'Scene ID is required.'
    return
  }
  try {
    errorMessage.value = ''
    const rawContext = await fetchSceneContext(sceneId.value, branchId.value)
    const context = unwrapData(rawContext) as Record<string, unknown>
    const resolvedSceneId = readString(context, 'id') ?? sceneId.value
    const resolvedTitle = readString(context, 'title') ?? store.title
    const resolvedSummary =
      readString(context, 'summary') ??
      readString(context, 'expected_outcome') ??
      ''
    const resolvedOutcome =
      readString(context, 'outcome') ??
      readString(context, 'actual_outcome') ??
      (store.outcome || 'success')
    const resolvedContent =
      readString(context, 'content') ??
      readString(context, 'rendered_content') ??
      resolvedSummary
    store.setScene(resolvedSceneId, resolvedTitle, resolvedSummary, resolvedOutcome, resolvedContent)
    const rootIdValue = requireProjectRootId()
    const branchIdValue = requireProjectBranchId()
    projectStore.setCurrentProject(rootIdValue, branchIdValue, resolvedSceneId)
    title.value = resolvedTitle
    summary.value = resolvedSummary
    outcome.value = resolvedOutcome
    content.value = resolvedContent
    notes.value = store.notes
    sceneContext.value = context
    const renderPayload = buildRenderPayload(sceneContext.value)
    const rendered = (await renderScene(resolvedSceneId, branchId.value, renderPayload)) as { content?: string }
    renderedContent.value = rendered.content ?? ''
  } catch (error) {
    errorMessage.value = 'Failed to load scene.'
  }
}

const saveScene = async () => {
  if (!hasSceneId.value) {
    errorMessage.value = 'Scene ID is required.'
    return
  }
  const nextSummary = store.summary.trim()
  if (!nextSummary) {
    errorMessage.value = 'Summary is required.'
    return
  }
  store.startSaving()
  try {
    errorMessage.value = ''
    const nextOutcome = store.outcome.trim() || 'success'
    store.outcome = nextOutcome
    outcome.value = nextOutcome
    await updateScene(sceneId.value, branchId.value, {
      outcome: nextOutcome,
      summary: nextSummary,
    })
    const nextConflictType = readString(sceneContext.value, 'conflict_type') ?? 'internal'
    await projectStore.saveProjectData(requireProjectRootId(), {
      expected_outcome: nextSummary,
      conflict_type: nextConflictType,
      actual_outcome: nextOutcome,
      summary: nextSummary,
      rendered_content: content.value,
    })
    store.markSaved(new Date().toISOString())
  } catch (error) {
    errorMessage.value = 'Failed to save scene.'
  } finally {
    store.finishSaving()
  }
}

const diffSceneView = async () => {
  if (!hasSceneId.value) {
    errorMessage.value = 'Scene ID is required.'
    return
  }
  try {
    errorMessage.value = ''
    const diffResult = (await diffScene(sceneId.value, branchId.value, fromCommitId.value, toCommitId.value)) as { diff?: string }
    diffContent.value = diffResult.diff ?? ''
    store.markDirty()
  } catch (error) {
    errorMessage.value = 'Failed to diff scene.'
  }
}

const renderSceneView = async () => {
  if (!hasSceneId.value) {
    errorMessage.value = 'Scene ID is required.'
    return
  }
  try {
    errorMessage.value = ''
    const renderPayload = buildRenderPayload(sceneContext.value)
    const rendered = (await renderScene(sceneId.value, branchId.value, renderPayload)) as { content?: string }
    renderedContent.value = rendered.content ?? ''
    content.value = renderedContent.value
    store.updateContent(content.value)
  } catch (error) {
    errorMessage.value = 'Failed to render scene.'
  }
}
</script>

<style scoped>
.header {
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
  align-items: center;
  gap: 8px;
}

.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 12px;
}

.empty-panel {
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  padding: 12px;
}

.error-panel {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #b91c1c;
}

.field {
  display: grid;
  gap: 6px;
}

.label {
  font-size: 12px;
  color: #6b7280;
}

.output {
  margin: 0;
  min-height: 48px;
  background: #f9fafb;
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
}

.dirty {
  font-weight: 600;
  color: #b45309;
}

.saving {
  font-weight: 600;
  color: #2563eb;
}

.scene-select {
  display: grid;
  gap: 8px;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}

input,
textarea,
select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
}

.chapter-review-list {
  display: grid;
  gap: 12px;
}

.chapter-review-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  display: grid;
  gap: 8px;
}

.chapter-review-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chapter-review-title {
  font-weight: 600;
}

.chapter-review-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chapter-render-actions {
  display: flex;
  align-items: center;
}

.chapter-render-error {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #b91c1c;
}

.version-control-grid {
  display: grid;
  gap: 12px;
}

.version-control-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  display: grid;
  gap: 8px;
}

.version-control-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.version-control-list {
  margin: 0;
  padding-left: 16px;
  color: #374151;
}

.version-control-current {
  margin: 0;
  font-weight: 600;
}

.snapshot-status {
  color: #047857;
  font-weight: 600;
}

.empty {
  color: #9ca3af;
  font-size: 13px;
}
</style>

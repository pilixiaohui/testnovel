import { defineStore } from 'pinia'
import { fetchSceneContext } from '../api/scene'
import { useProjectStore } from './project'

interface EditorStoreState {
  scene_id: string
  title: string
  summary: string
  outcome: string
  notes: string
  content: string
  is_saving: boolean
  is_dirty: boolean
  last_saved_at: string
}

const normalizeScenePayload = (payload: unknown): Record<string, unknown> => {
  let normalized = payload
  if (typeof normalized === 'string') {
    try {
      normalized = JSON.parse(normalized) as unknown
    } catch (error) {
      throw new Error('scene payload is required')
    }
  }
  const data = (normalized as { data?: unknown }).data ?? normalized
  if (!data || typeof data !== 'object') {
    throw new Error('scene payload is required')
  }
  return data as Record<string, unknown>
}

const readRequiredString = (record: Record<string, unknown>, key: string, label: string) => {
  const value = record[key]
  if (typeof value !== 'string') {
    throw new Error(label)
  }
  return value
}

const readSceneContent = (record: Record<string, unknown>) => {
  const content = record.content
  if (typeof content === 'string') {
    return content
  }
  const rendered = record.rendered_content
  if (typeof rendered === 'string') {
    return rendered
  }
  throw new Error('scene content is required')
}

export const useEditorStore = defineStore('editor', {
  state: (): EditorStoreState => ({
    scene_id: '',
    title: '',
    summary: '',
    outcome: 'success',
    notes: '',
    content: '',
    is_saving: false,
    is_dirty: false,
    last_saved_at: '',
  }),
  getters: {
    /* c8 ignore next */
    hasScene: (state: EditorStoreState) => state.scene_id.length > 0,
  },
  actions: {
    setScene(scene_id: string, title: string, summary: string, outcome: string, content: string) {
      this.scene_id = scene_id
      this.title = title
      this.summary = summary
      this.outcome = outcome
      this.content = content
      this.is_dirty = false
    },
    async selectScene(sceneId: string) {
      if (!sceneId) {
        throw new Error('scene_id is required')
      }
      const projectStore = useProjectStore()
      if (!projectStore.branch_id) {
        throw new Error('branch_id is required')
      }
      const payload = await fetchSceneContext(sceneId, projectStore.branch_id)
      const record = normalizeScenePayload(payload)
      const id = readRequiredString(record, 'id', 'scene id is required')
      const title = readRequiredString(record, 'title', 'scene title is required')
      const summary = readRequiredString(record, 'summary', 'scene summary is required')
      const outcome = readRequiredString(record, 'outcome', 'scene outcome is required')
      const content = readSceneContent(record)
      this.setScene(id, title, summary, outcome, content)
    },
    /* c8 ignore next 3 */
    updateTitle(title: string) {
      this.title = title
      this.is_dirty = true
    },
    updateSummary(summary: string) {
      this.summary = summary
      this.is_dirty = true
    },
    updateOutcome(outcome: string) {
      this.outcome = outcome
      this.is_dirty = true
    },
    /* c8 ignore next 3 */
    updateNotes(notes: string) {
      this.notes = notes
      this.is_dirty = true
    },
    updateContent(content: string) {
      this.content = content
      this.is_dirty = true
    },
    startSaving() {
      this.is_saving = true
    },
    finishSaving() {
      this.is_saving = false
    },
    markDirty() {
      this.is_dirty = true
    },
    markSaved(timestamp: string) {
      this.last_saved_at = timestamp
      this.is_dirty = false
    },
    /* c8 ignore next 8 */
    reset() {
      this.scene_id = ''
      this.title = ''
      this.summary = ''
      this.outcome = 'success'
      this.notes = ''
      this.content = ''
      this.is_saving = false
      this.is_dirty = false
      this.last_saved_at = ''
    },
  },
})

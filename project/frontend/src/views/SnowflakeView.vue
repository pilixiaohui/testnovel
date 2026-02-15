<template>
  <section class="page" data-test="snowflake-flow-root">
    <header class="header">
      <div>
        <h1>Snowflake Flow</h1>
        <p class="subtitle">Build the six-step outline from idea to anchors.</p>
      </div>
      <div class="actions">
        <button type="button" data-test="snowflake-add-step">Add Step</button>
        <button type="button" data-test="save-project-btn" @click="saveUpdates">Save</button>
        <button type="button" data-test="snowflake-reset" @click="resetFlow">Reset</button>
      </div>
    </header>

    <div class="status">
      <span v-if="isDirty" data-test="snowflake-dirty" class="dirty-pill">Unsaved changes</span>
      <p v-if="errorMessage" data-test="snowflake-error" class="error-text">{{ errorMessage }}</p>
    </div>

    <section class="prompt-controls" data-test="snowflake-prompt-controls">
      <div class="prompt-header">
        <h2>Prompt Settings</h2>
        <div class="prompt-actions">
          <button type="button" data-test="snowflake-prompt-save" @click="savePrompts">
            Save Prompts
          </button>
          <button type="button" data-test="snowflake-prompt-reset" @click="resetPrompts">
            Reset Prompts
          </button>
        </div>
      </div>
      <p class="prompt-hint">Customize the system prompts for each snowflake step.</p>
    </section>

    <StateExtractPanel :root-id="extractRootId" :branch-id="extractBranchId" :context="stateExtractContext" />

    <section class="steps" data-test="snowflake-step-list">
      <h2>Six-Step Outline</h2>
      <ol>
        <li>Step 1 · Logline ({{ store.logline.length }})</li>
        <li>Step 2 · Root ({{ store.root ? 'ready' : 'empty' }})</li>
        <li>Step 3 · Characters ({{ store.characters.length }})</li>
        <li>Step 4 · Scenes ({{ store.scenes.length }})</li>
        <li>Step 5 · Acts/Chapters ({{ store.acts.length }}/{{ store.chapters.length }})</li>
        <li>Step 6 · Anchors ({{ store.anchors.length }})</li>
      </ol>
    </section>

    <section class="step-panel">
      <h3>Step 1 · Logline</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step1"
          data-test="snowflake-step1-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 1"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <input
        v-model="idea"
        data-test="snowflake-idea-input"
        type="text"
        placeholder="Describe your story idea"
      />
      <button type="button" data-test="snowflake-step1-submit" @click="runStep(1)">Run Step 1</button>
      <div class="result-list">
        <input
          v-for="(line, index) in store.steps.logline"
          :key="`logline-${index}-${line}`"
          v-model="store.steps.logline[index]"
          data-test="snowflake-logline-input"
          type="text"
          @input="markDirty"
        />
      </div>
      <pre
        v-if="store.logline.length"
        class="detail-block"
        data-test="snowflake-step1-raw"
      >{{ JSON.stringify(store.logline, null, 2) }}</pre>
    </section>

    <section class="step-panel">
      <h3>Step 2 · Root</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step2"
          data-test="snowflake-step2-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 2"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <select v-model="selectedLogline" data-test="snowflake-logline-select">
        <option v-for="line in store.logline" :key="line" :value="line">{{ line }}</option>
      </select>
      <button type="button" data-test="snowflake-step2-submit" @click="runStep(2)">Run Step 2</button>
      <p class="result-text">{{ store.root?.logline }}</p>
      <div v-if="store.root" class="detail-grid">
        <p data-test="snowflake-root-theme"><strong>Theme:</strong> {{ store.root.theme }}</p>
        <p data-test="snowflake-root-ending"><strong>Ending:</strong> {{ store.root.ending }}</p>
        <p data-test="snowflake-root-disasters">
          <strong>Three Disasters:</strong> {{ store.root.three_disasters.join(' | ') }}
        </p>
      </div>
      <pre v-if="store.root" class="detail-block" data-test="snowflake-root-details">{{ JSON.stringify(store.root, null, 2) }}</pre>
    </section>

    <section class="step-panel">
      <h3>Step 3 · Characters</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step3"
          data-test="snowflake-step3-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 3"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <button type="button" data-test="snowflake-step3-submit" @click="runStep(3)">Run Step 3</button>
      <ul class="result-list" data-test="step3-character-details">
        <li v-for="character in store.characters" :key="character.id ?? character.entity_id ?? character.name">
          <input
            v-model="character.name"
            data-test="snowflake-character-name-input"
            type="text"
            @input="markDirty"
          />
          <div class="detail-grid">
            <p data-test="snowflake-character-ambition">
              <strong>Ambition:</strong> <span data-test="character-ambition">{{ character.ambition }}</span>
            </p>
            <p data-test="snowflake-character-conflict">
              <strong>Conflict:</strong> <span data-test="character-conflict">{{ character.conflict }}</span>
            </p>
            <p data-test="snowflake-character-epiphany">
              <strong>Epiphany:</strong> <span data-test="character-epiphany">{{ character.epiphany }}</span>
            </p>
            <p data-test="snowflake-character-voice-dna">
              <strong>Voice DNA:</strong> <span data-test="character-voice-dna">{{ character.voice_dna }}</span>
            </p>
            <p data-test="snowflake-character-summary">
              <strong>Summary:</strong> {{ character.one_sentence_summary }}
            </p>
          </div>
          <pre class="detail-block" data-test="snowflake-character-details">{{ JSON.stringify(character, null, 2) }}</pre>
        </li>
      </ul>
    </section>

    <section class="step-panel">
      <h3>Step 4 · Scenes</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step4"
          data-test="snowflake-step4-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 4"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <button type="button" data-test="snowflake-step4-submit" @click="runStep(4)">Run Step 4</button>
      <ul class="result-list" data-test="step4-scene-details">
        <li v-for="scene in store.scenes" :key="scene.id">
          <input
            v-model="scene.title"
            data-test="snowflake-scene-title-input"
            type="text"
            @input="markDirty"
          />
          <div class="detail-grid">
            <p data-test="snowflake-scene-sequence-index"><strong>Sequence:</strong> {{ scene.sequence_index }}</p>
            <p data-test="snowflake-scene-expected-outcome"><strong>Expected:</strong> {{ scene.expected_outcome }}</p>
            <p data-test="snowflake-scene-conflict-type"><strong>Conflict Type:</strong> {{ scene.conflict_type }}</p>
            <p data-test="snowflake-scene-actual-outcome"><strong>Actual:</strong> {{ scene.actual_outcome }}</p>
          </div>
          <pre class="detail-block" data-test="snowflake-scene-details">{{ JSON.stringify(scene, null, 2) }}</pre>
        </li>
      </ul>
    </section>

    <section class="step-panel">
      <h3>Step 5 · Acts & Chapters</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step5"
          data-test="snowflake-step5-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 5"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <button type="button" data-test="snowflake-step5-submit" @click="runStep(5)">Run Step 5</button>
      <p class="result-text">Acts: {{ store.acts.length }}, Chapters: {{ store.chapters.length }}</p>
      <div class="result-list" data-test="step5-act-chapter-details">
        <div v-for="act in store.acts" :key="act.id">
          <input
            v-model="act.title"
            data-test="snowflake-act-title-input"
            type="text"
            @input="markDirty"
          />
          <div class="detail-grid">
            <p data-test="snowflake-act-purpose"><strong>Purpose:</strong> {{ act.purpose }}</p>
            <p data-test="snowflake-act-tone"><strong>Tone:</strong> {{ act.tone }}</p>
          </div>
          <pre class="detail-block" data-test="snowflake-act-details">{{ JSON.stringify(act, null, 2) }}</pre>
        </div>
        <div v-for="chapter in store.chapters" :key="chapter.id">
          <input
            v-model="chapter.title"
            data-test="snowflake-chapter-title-input"
            type="text"
            @input="markDirty"
          />
          <div class="detail-grid">
            <p data-test="snowflake-chapter-focus"><strong>Focus:</strong> {{ chapter.focus }}</p>
            <p data-test="snowflake-chapter-pov"><strong>POV:</strong> {{ chapter.pov_character_id }}</p>
            <p data-test="snowflake-chapter-word-count"><strong>Word Count:</strong> {{ chapter.word_count ?? '' }}</p>
          </div>
          <pre class="detail-block" data-test="snowflake-chapter-details">{{ JSON.stringify(chapter, null, 2) }}</pre>
        </div>
      </div>
      <pre
        v-if="store.acts.length || store.chapters.length"
        class="detail-block"
        data-test="snowflake-step5-raw"
      >{{ JSON.stringify({ acts: store.acts, chapters: store.chapters }, null, 2) }}</pre>
    </section>

    <section class="step-panel">
      <h3>Step 6 · Anchors</h3>
      <div class="prompt-editor">
        <label class="prompt-label">Prompt</label>
        <textarea
          v-model="prompts.step6"
          data-test="snowflake-step6-prompt-input"
          rows="3"
          placeholder="Edit prompt for step 6"
          @input="markPromptDirty"
        ></textarea>
      </div>
      <button type="button" data-test="snowflake-step6-submit" @click="runStep(6)">Run Step 6</button>
      <p class="result-text">Anchors: {{ store.anchors.length }}</p>
      <div class="result-list" data-test="step6-anchor-details">
        <div v-for="(anchor, index) in store.anchors" :key="`anchor-${index}`" data-test="snowflake-anchor-item">
          <div class="detail-grid">
            <p data-test="snowflake-anchor-type"><strong>Type:</strong> {{ readAnchorText(anchor, 'anchor_type') }}</p>
            <p data-test="snowflake-anchor-description"><strong>Description:</strong> {{ readAnchorText(anchor, 'description') }}</p>
            <p data-test="snowflake-anchor-constraint"><strong>Constraint:</strong> {{ readAnchorText(anchor, 'constraint_type') }}</p>
            <p data-test="snowflake-anchor-conditions">
              <strong>Required Conditions:</strong> {{ readAnchorConditions(anchor).join(', ') }}
            </p>
            <p data-test="snowflake-anchor-achieved">
              <strong>Achieved:</strong> {{ readAnchorAchieved(anchor) ? '是' : '否' }}
            </p>
          </div>
          <pre class="detail-block" data-test="snowflake-anchor-details">{{ JSON.stringify(anchor, null, 2) }}</pre>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { useSnowflakeStore } from '../stores/snowflake'
import {
  fetchSnowflakePrompts,
  resetSnowflakePrompts,
  saveSnowflakePrompts,
} from '../api/snowflake'
import StateExtractPanel from '../components/StateExtractPanel.vue'
import type {
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakePromptSet,
  SnowflakeStep5Payload,
  SnowflakeSceneNode,
  SnowflakeStructure,
  SnowflakeAnchor,
} from '../types/snowflake'

const store = useSnowflakeStore()
const router = useRouter()
const projectStore = useProjectStore()
const idea = ref('')
const selectedLogline = ref('')
const step4RootId = ref('')
const step4BranchId = ref('')
const step4ResultPromise = ref<Promise<SnowflakeStep4Result> | null>(null)
const extractRootId = computed(() => step4RootId.value || store.id || projectStore.root_id)
const extractBranchId = computed(() => step4BranchId.value || projectStore.branch_id || 'main')
const contentDirty = ref(false)
const promptDirty = ref(false)
const isDirty = computed(() => contentDirty.value || promptDirty.value)
const errorMessage = ref('')
const emptyPrompts: SnowflakePromptSet = {
  step1: '',
  step2: '',
  step3: '',
  step4: '',
  step5: '',
  step6: '',
}

const prompts = reactive<SnowflakePromptSet>({ ...emptyPrompts })

const readNonEmpty = (value: unknown) =>
  typeof value === 'string' && value.trim().length > 0 ? value.trim() : ''

const requireNonEmpty = (value: unknown, label: string) => {
  const trimmed = readNonEmpty(value)
  if (!trimmed) {
    throw new Error(`${label} is required`)
  }
  return trimmed
}

const requireInteger = (value: unknown, label: string) => {
  if (!Number.isInteger(value)) {
    throw new Error(`${label} is required`)
  }
  return value as number
}

const normalizeOptionalString = (value: unknown, label: string) => {
  if (value === undefined || value === null) {
    return ''
  }
  if (typeof value !== 'string') {
    throw new Error(`${label} is required`)
  }
  return value
}

const normalizeSceneForSave = (scene: SnowflakeSceneNode): SnowflakeSceneNode => ({
  ...scene,
  id: requireNonEmpty(scene.id, 'scene.id'),
  title: requireNonEmpty(scene.title, 'scene.title'),
  sequence_index: requireInteger(scene.sequence_index, 'scene.sequence_index'),
  expected_outcome: requireNonEmpty(scene.expected_outcome, 'scene.expected_outcome'),
  conflict_type: requireNonEmpty(scene.conflict_type, 'scene.conflict_type'),
  pov_character_id: requireNonEmpty(scene.pov_character_id, 'scene.pov_character_id'),
  actual_outcome: normalizeOptionalString(scene.actual_outcome, 'scene.actual_outcome'),
})

const readAnchorText = (anchor: SnowflakeAnchor, key: string) => {
  const value = anchor[key]
  return typeof value === 'string' ? value : ''
}

const readAnchorAchieved = (anchor: SnowflakeAnchor) => {
  const value = anchor.achieved
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'string') {
    return value === 'true'
  }
  return false
}

const readAnchorConditions = (anchor: SnowflakeAnchor) => {
  const value: unknown = anchor.required_conditions
  const source = typeof value === 'string' ? (JSON.parse(value) as unknown) : value
  if (!Array.isArray(source)) {
    throw new Error('required_conditions must be an array')
  }
  return source.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

const stateExtractContext = computed(() => {
  const sceneTitles = store.steps.scenes
    .map((scene) => readNonEmpty(scene.title))
    .filter((value) => value.length > 0)
    .join('\n')

  const content =
    readNonEmpty(sceneTitles) ||
    readNonEmpty(store.steps.root?.logline) ||
    readNonEmpty(selectedLogline.value) ||
    readNonEmpty(idea.value)

  const entityIds = store.steps.characters
    .map((character) => readNonEmpty(character.id || character.entity_id))
    .filter((value) => value.length > 0)

  return {
    content,
    summary: readNonEmpty(store.steps.root?.theme),
    entity_ids: entityIds,
    scene_entities: entityIds.map((entityId) => ({ entity_id: entityId })),
  }
})

const markDirty = () => {
  contentDirty.value = true
  errorMessage.value = ''
}

const markPromptDirty = () => {
  promptDirty.value = true
  errorMessage.value = ''
}

const requireRootForStep = (step: number): SnowflakeStructure => {
  const root = store.root
  if (!root) {
    throw new Error(`step${step} requires root`)
  }
  if (!Array.isArray(root.three_disasters) || root.three_disasters.length !== 3) {
    throw new Error('three_disasters is required, run step2 first')
  }
  return root
}

const applyPromptValues = (values: SnowflakePromptSet) => {
  Object.assign(prompts, values)
}

const savePrompts = async () => {
  errorMessage.value = ''
  try {
    if (!projectStore.root_id) {
      throw new Error('root_id is required for snowflake prompt save')
    }
    if (!projectStore.branch_id) {
      throw new Error('branch_id is required for snowflake prompt save')
    }
    await saveSnowflakePrompts(projectStore.root_id, projectStore.branch_id, { ...prompts })
    promptDirty.value = false
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

const resetPrompts = async () => {
  errorMessage.value = ''
  try {
    if (!projectStore.root_id) {
      throw new Error('root_id is required for snowflake prompt reset')
    }
    if (!projectStore.branch_id) {
      throw new Error('branch_id is required for snowflake prompt reset')
    }
    const defaults = (await resetSnowflakePrompts(
      projectStore.root_id,
      projectStore.branch_id,
    )) as SnowflakePromptSet
    applyPromptValues(defaults)
    promptDirty.value = false
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

const saveUpdates = async () => {
  errorMessage.value = ''
  try {
    if (!projectStore.root_id) {
      throw new Error('root_id is required for snowflake save')
    }


    const normalizedCharacters = store.steps.characters.map((character) => {
      const characterId = character.id || character.entity_id
      if (!characterId) {
        throw new Error('character_id is required for snowflake character save')
      }
      return {
        ...character,
        id: characterId,
        entity_id: characterId,
      }
    })

    store.steps.characters = normalizedCharacters

    const preparedScenes =
      store.steps.scenes.length > 0 ? store.steps.scenes.map(normalizeSceneForSave) : []

    await store.saveStepToBackend('step1', { logline: [...store.steps.logline] })

    if (store.steps.root) {
      await store.saveStepToBackend('step2', { root: { ...store.steps.root } })
    }

    if (normalizedCharacters.length > 0) {
      await store.saveStepToBackend('step3', { characters: normalizedCharacters })
    }

    if (preparedScenes.length > 0) {
      await store.saveStepToBackend('step4', {
        scenes: preparedScenes.map((scene) => ({ ...scene })),
      })
    }

    if (store.steps.acts.length > 0 || store.steps.chapters.length > 0) {
      await store.saveStepToBackend('step5', {
        acts: store.steps.acts.map((act) => ({ ...act })),
        chapters: store.steps.chapters.map((chapter) => ({ ...chapter })),
      })
    }

    if (store.steps.anchors.length > 0) {
      await store.saveStepToBackend('step6', {
        anchors: store.steps.anchors.map((anchor) => ({ ...anchor })),
      })
    }

    if (promptDirty.value) {
      await saveSnowflakePrompts(projectStore.root_id, projectStore.branch_id, { ...prompts })
      promptDirty.value = false
    }

    contentDirty.value = false
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

const loadSnowflakeContext = async (rootId: string, branchId: string) => {
  if (!rootId) {
    store.reset()
    selectedLogline.value = ''
    step4RootId.value = ''
    step4BranchId.value = ''
    step4ResultPromise.value = null
    contentDirty.value = false
    promptDirty.value = false
    applyPromptValues(emptyPrompts)
    errorMessage.value = ''
    return
  }

  if (!branchId) {
    errorMessage.value = 'branch_id is required for snowflake prompts'
    return
  }

  errorMessage.value = ''

  try {
    await store.loadProgress(rootId, branchId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }

  try {
    const currentPrompts = (await fetchSnowflakePrompts(rootId, branchId)) as SnowflakePromptSet
    applyPromptValues(currentPrompts)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }

  if (!selectedLogline.value && store.logline.length > 0) {
    selectedLogline.value = store.logline[0]!
  }
}

watch(
  () => [projectStore.root_id, projectStore.branch_id] as const,
  ([rootId, branchId]) => {
    void loadSnowflakeContext(rootId, branchId)
  },
  { immediate: true },
)

const runStep = async (step: number) => {
  errorMessage.value = ''
  try {
    switch (step) {
      case 1: {
        const trimmedIdea = idea.value.trim()
        if (!trimmedIdea) {
          errorMessage.value = 'idea is required'
          return
        }
        const loglines = await store.fetchStep1(trimmedIdea, { prompt: prompts.step1 })
        selectedLogline.value = loglines[0] || ''
        return
      }
      case 2: {
        const trimmedLogline = selectedLogline.value.trim()
        if (!trimmedLogline) {
          errorMessage.value = 'logline is required'
          return
        }
        await store.fetchStep2(trimmedLogline, { prompt: prompts.step2 })
        return
      }
      case 3: {
        const root = requireRootForStep(step)
        await store.fetchStep3(root, { prompt: prompts.step3 })
        return
      }
      case 4: {
        const root = requireRootForStep(step)
        const payload: SnowflakeStep4Payload = {
          root,
          characters: store.characters,
        }
        const promise = store.fetchStep4(payload, { prompt: prompts.step4 }) as Promise<SnowflakeStep4Result>
        step4ResultPromise.value = promise
        const result = await promise
        if (!result.root_id) {
          throw new Error('root_id is required for step4')
        }
        if (!result.branch_id) {
          throw new Error('branch_id is required for step4')
        }
        step4RootId.value = result.root_id
        step4BranchId.value = result.branch_id
        projectStore.setProject(result.root_id, result.branch_id)
        return
      }
      case 5: {
        const root = requireRootForStep(step)
        if (step4ResultPromise.value) {
          const result = await step4ResultPromise.value
          step4RootId.value = result.root_id
        }
        if (!step4RootId.value) {
          throw new Error('root_id is required for step5, run step4 first')
        }
        const payload: SnowflakeStep5Payload = {
          root_id: step4RootId.value,
          root,
          characters: store.characters,
        }
        await store.fetchStep5(payload, { prompt: prompts.step5 })
        return
      }
      case 6: {
        if (store.acts.length === 0) {
          throw new Error('acts are required for anchors, run step5 first')
        }
        const targetRootId = step4RootId.value || store.id
        const targetBranchId = step4BranchId.value || 'main'
        await store.fetchStep6(targetBranchId, { prompt: prompts.step6 })
        await router.push({ path: '/editor', query: { root_id: targetRootId, branch_id: targetBranchId } })
        return
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

const resetFlow = () => {
  store.reset()
  idea.value = ''
  selectedLogline.value = ''
  step4RootId.value = ''
  step4BranchId.value = ''
  step4ResultPromise.value = null
  contentDirty.value = false
  errorMessage.value = ''
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
  gap: 8px;
}

.status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prompt-controls {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 8px;
}

.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.prompt-actions {
  display: flex;
  gap: 8px;
}

.prompt-hint {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

.prompt-editor {
  display: grid;
  gap: 6px;
}

.prompt-label {
  font-size: 13px;
  color: #6b7280;
}

.dirty-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 9999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 12px;
}

.error-text {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
}

.steps {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
}

.step-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 8px;
}

.result-list {
  margin: 0;
  padding-left: 16px;
  color: #374151;
}

.result-text {
  margin: 0;
  color: #374151;
}

.detail-grid {
  display: grid;
  gap: 6px;
  padding: 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px dashed #e5e7eb;
}

.detail-grid p {
  margin: 0;
  font-size: 12px;
  color: #374151;
}

.detail-block {
  margin: 8px 0 0;
  padding: 8px;
  border-radius: 8px;
  background: #f9fafb;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}

input,
select,
textarea {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
}
</style>

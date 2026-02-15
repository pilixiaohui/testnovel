<template>
  <section class="page" data-test="simulation-console-root">
    <header class="header">
      <div>
        <h1>Simulation Console</h1>
        <p class="subtitle" data-test="simulation-status">Status: {{ status }}</p>
      </div>
      <div class="controls">
        <button type="button" data-test="simulation-start" :disabled="!hasSceneId" @click="startSimulation">Start</button>
        <button type="button" data-test="simulation-stop" :disabled="!hasSceneId" @click="stopSimulation">Stop</button>
        <button type="button" data-test="simulation-reset" :disabled="!hasSceneId" @click="resetSimulation">Reset</button>
      </div>
    </header>

    <ApiFeedback :loading="apiLoading" :error="apiError" />

    <section class="panel" data-test="simulation-scene-panel">
      <h2>Scenes</h2>
      <div v-if="!hasProjectContext" class="empty-panel" data-test="simulation-scene-context-missing">
        <strong>Project context required.</strong>
        <p class="subtitle">Select a project and branch to load scenes.</p>
      </div>
      <div v-else-if="sceneListError" class="empty-panel" data-test="simulation-scene-error">
        <strong>Unable to load scenes.</strong>
        <p class="subtitle">{{ sceneListError }}</p>
      </div>
      <div v-else-if="sceneOptions.length === 0" class="empty-panel" data-test="simulation-scene-empty">
        <strong>No scenes yet.</strong>
        <p class="subtitle">Generate scenes in Snowflake step 4 first.</p>
      </div>
      <div v-else class="scene-select">
        <label class="field">
          <span class="label">Select Scene</span>
          <select
            v-model="selectedSceneId"
            data-test="simulation-scene-select"
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

    <section v-if="!hasSceneId" class="panel empty-panel" data-test="simulation-empty">
      <strong>Scene required.</strong>
      <p class="subtitle">Select a scene before running simulations.</p>
    </section>

    <section class="run-controls">
      <button type="button" class="full" data-test="simulation-step" :disabled="!hasSceneId" @click="stepSimulation">
        Step
      </button>
      <button type="button" class="full" data-test="simulation-scene" :disabled="!hasSceneId" @click="runSceneSimulation">
        Scene
      </button>
      <button type="button" class="full" data-test="run-simulation-btn" :disabled="!hasSceneId" @click="runSceneSimulation">
        运行推演
      </button>
      <span v-if="converged" class="converged" data-test="simulation-converged">Converged</span>
    </section>

    <section class="panel" data-test="simulation-results">
      <h2>Logs</h2>
      <div class="log-panel" data-test="simulation-log">
        <div v-for="log in logs" :key="log.id" class="log-line">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-text">{{ log.text }}</span>
        </div>
      </div>
    </section>

    <section v-if="rounds.length" class="panel" data-test="simulation-rounds">
      <h2>Rounds</h2>
      <div data-test="simulation-round-player">
        <RoundPlayer :current-round="currentRound" :total-rounds="rounds.length" :is-playing="isPlaying" />
      </div>
      <div data-test="simulation-timeline">
        <ActionTimeline :rounds="rounds" />
      </div>
    </section>

    <section class="panel" data-test="simulation-agents">
      <h2>Agents</h2>
      <ConvergenceIndicator v-if="convergence" :convergence="convergence" />
      <div v-if="!hasProjectContext" class="empty-panel" data-test="simulation-context-missing">
        <strong>Project context required.</strong>
        <p class="subtitle">Select a project and branch to load agents.</p>
      </div>
      <div v-else-if="agentLoadError" class="empty-panel" data-test="simulation-error">
        <strong>Unable to load agents.</strong>
        <p class="subtitle">Please retry after checking the simulation service.</p>
      </div>
      <div v-else-if="agents.length === 0" class="empty-panel" data-test="simulation-agents-empty">
        <strong>No agents yet.</strong>
        <p class="subtitle">Run a simulation round to populate agent state.</p>
      </div>
      <div v-else data-test="simulation-agent-state">
        <AgentStatePanel :agent-state="agentState" />
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ActionTimeline from '../components/simulation/ActionTimeline.vue'
import AgentStatePanel from '../components/simulation/AgentStatePanel.vue'
import RoundPlayer from '../components/simulation/RoundPlayer.vue'
import ConvergenceIndicator from '../components/simulation/ConvergenceIndicator.vue'
import ApiFeedback from '../components/ApiFeedback.vue'
import { useSimulationStore } from '../stores/simulation'
import { useProjectStore } from '../stores/project'
import { fetchSceneContext, fetchScenes } from '@/api/scene'
import { agentApi } from '@/api/agent'
import * as simulationApi from '@/api/simulation'
import type {
  CharacterAgentState,
  ConvergenceCheck,
  SimulationConfig,
  SimulationRoundResult,
} from '../types/simulation'

interface SimulationLogItem {
  id: string
  time: string
  text: string
}

type SimulationAgentsConvergence = { score: number; check: ConvergenceCheck } | ConvergenceCheck

type SimulationAgentsResponse = {
  agents?: unknown
  convergence?: SimulationAgentsConvergence
}

const store = useSimulationStore()
const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()

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
const status = computed(() => store.status)
const sceneId = computed(() => {
  const fromRoute = resolveRouteString(route.params.sceneId)
  if (fromRoute) {
    return fromRoute
  }
  if (projectStore.scene_id) {
    return projectStore.scene_id
  }
  return ''
})
const hasSceneId = computed(() => sceneId.value.length > 0)
const hasProjectContext = computed(() => Boolean(projectStore.root_id && projectStore.branch_id))
const branchId = computed(() => {
  const value = projectStore.branch_id
  if (!value) {
    throw new Error('branch_id is required')
  }
  return value
})
const sceneContext = ref<Record<string, unknown>>({})
const sceneListLoading = ref(false)
const agentsLoading = ref(false)
const sceneListError = ref('')
const sceneOptions = ref<Array<{ id: string; label: string }>>([])
const selectedSceneId = ref('')
const agents = ref<CharacterAgentState[]>([])
const convergence = ref<SimulationAgentsConvergence | null>(null)
const agentLoadError = ref<Error | null>(null)

const apiLoading = computed(() => sceneListLoading.value || agentsLoading.value)
const apiError = computed(() => {
  if (sceneListError.value) {
    return sceneListError.value
  }
  if (agentLoadError.value) {
    return agentLoadError.value.message
  }
  return ''
})
const logs = ref<SimulationLogItem[]>([])
const converged = ref(false)
const rounds = ref<SimulationRoundResult[]>([])
const currentRound = ref(1)
const isPlaying = ref(false)
const agentState = computed<CharacterAgentState>(() => {
  const first = agents.value[0]
  if (!first) {
    throw new Error('agent state is required')
  }
  return first
})

const buildLogs = (configs: SimulationConfig[]) =>
  configs.map((config, index) => ({
    id: config.round_id || `log-${index}`,
    time: config.round_id || 'pending',
    text: `Loaded ${config.round_id || 'round'}`,
  }))

const resolveRequestErrorMessage = (error: unknown, fallbackMessage: string) => {
  const response = (error as { response?: { status?: unknown; data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail
  }
  if (typeof response?.status === 'number') {
    return `Request failed with status ${response.status}`
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }
  return fallbackMessage
}

const SCENE_ID_PATTERN = /^[A-Za-z0-9-]{1,64}$/

const assertValidSceneId = (value: string) => {
  if (!SCENE_ID_PATTERN.test(value)) {
    throw new Error('scene_id format is invalid')
  }
}

const assertSceneInProject = (value: string) => {
  if (sceneOptions.value.length === 0) {
    return
  }
  if (!sceneOptions.value.some((scene) => scene.id === value)) {
    throw new Error('scene_id not found in current project')
  }
}

const resolveWorldState = (context: Record<string, unknown>) => {
  const candidate = context.world_state
  if (candidate && typeof candidate === 'object' && !Array.isArray(candidate)) {
    return { ...(candidate as Record<string, unknown>) }
  }
  const semanticStates = context.semantic_states
  if (semanticStates && typeof semanticStates === 'object' && !Array.isArray(semanticStates)) {
    return { ...(semanticStates as Record<string, unknown>) }
  }
  throw new Error('world_state is required')
}

const normalizeSceneContext = (raw: unknown, fallbackSceneId: string) => {
  const normalized = typeof raw === 'string' ? (JSON.parse(raw) as unknown) : raw
  const context = (normalized as { data?: unknown }).data ?? normalized
  if (!context || typeof context !== 'object' || Array.isArray(context)) {
    throw new Error('scene context is required')
  }
  const contextRecord = { ...(context as Record<string, unknown>) }
  const existingSceneId =
    typeof contextRecord.scene_id === 'string' && contextRecord.scene_id.length > 0
      ? contextRecord.scene_id
      : typeof contextRecord.id === 'string' && contextRecord.id.length > 0
        ? contextRecord.id
        : fallbackSceneId
  if (typeof existingSceneId !== 'string' || existingSceneId.length === 0) {
    throw new Error('scene_id is required')
  }
  assertValidSceneId(existingSceneId)
  contextRecord.scene_id = existingSceneId
  if (!('scene' in contextRecord)) {
    const summary = typeof contextRecord.summary === 'string' ? contextRecord.summary : ''
    const expected =
      typeof contextRecord.expected_outcome === 'string' ? contextRecord.expected_outcome : ''
    contextRecord.scene = {
      scene_id: existingSceneId,
      summary,
      expected_outcome: expected,
    }
  }
  const needsWorldState =
    Boolean(contextRecord.root_id) || Boolean(contextRecord.branch_id) || Boolean(contextRecord.next_anchor)
  if (needsWorldState) {
    const worldState = resolveWorldState(contextRecord)
    if (typeof worldState['distance'] !== 'number') {
      worldState['distance'] = 1
    }
    contextRecord.world_state = worldState
  }

  return contextRecord
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
    const rootIdValue = projectStore.root_id
    const branchIdValue = projectStore.branch_id
    if (!rootIdValue || !branchIdValue) {
      throw new Error('root_id and branch_id are required')
    }
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
  const rootIdValue = projectStore.root_id
  const branchIdValue = projectStore.branch_id
  if (!rootIdValue || !branchIdValue) {
    throw new Error('root_id and branch_id are required')
  }
  projectStore.setCurrentProject(rootIdValue, branchIdValue, nextSceneId)
  await router.push({
    name: 'simulation',
    params: { sceneId: nextSceneId },
    query: { root_id: rootIdValue, branch_id: branchIdValue },
  })
}

const normalizeAgentState = (agent: Record<string, unknown>): CharacterAgentState => {
  const id = typeof agent.id === 'string' ? agent.id : ''
  const characterId = typeof agent.character_id === 'string' ? agent.character_id : ''
  if (!id || !characterId) {
    throw new Error('agent state is required')
  }
  const branchIdValue =
    typeof agent.branch_id === 'string' && agent.branch_id.trim().length > 0
      ? agent.branch_id
      : branchId.value
  if (!branchIdValue) {
    throw new Error('branch_id is required')
  }
  const beliefs = agent.beliefs
  const privateKnowledge = agent.private_knowledge
  return {
    id,
    character_id: characterId,
    branch_id: branchIdValue,
    beliefs:
      beliefs && typeof beliefs === 'object' && !Array.isArray(beliefs)
        ? (beliefs as Record<string, unknown>)
        : {},
    desires: Array.isArray(agent.desires) ? (agent.desires as CharacterAgentState['desires']) : [],
    intentions: Array.isArray(agent.intentions)
      ? (agent.intentions as CharacterAgentState['intentions'])
      : [],
    memory: Array.isArray(agent.memory) ? agent.memory : [],
    private_knowledge:
      privateKnowledge && typeof privateKnowledge === 'object' && !Array.isArray(privateKnowledge)
        ? (privateKnowledge as Record<string, unknown>)
        : {},
    last_updated_scene: typeof agent.last_updated_scene === 'number' ? agent.last_updated_scene : 0,
    version: typeof agent.version === 'number' ? agent.version : 1,
  }
}



const resolveAgentsPayload = (raw: unknown): SimulationAgentsResponse => {
  const normalized = (raw as { data?: unknown }).data ?? raw
  if (Array.isArray(normalized)) {
    return { agents: normalized }
  }
  if (normalized && typeof normalized === 'object') {
    return normalized as SimulationAgentsResponse
  }
  throw new Error('agents payload is required')
}

const fetchAgentsPayload = async () => {
  const rootIdValue = projectStore.root_id
  const branchIdValue = projectStore.branch_id
  if (!rootIdValue || !branchIdValue) {
    throw new Error('root_id and branch_id are required')
  }
  const payload = resolveAgentsPayload(
    await simulationApi.fetchSimulationAgents(rootIdValue, branchIdValue),
  )
  const list = payload.agents ?? []
  if (!Array.isArray(list)) {
    throw new Error('agents list is required')
  }
  if (list.length === 0) {
    return { agents: [], convergence: payload.convergence ?? null }
  }
  const agentIds = list.map((agent) => {
    const id = typeof agent.id === 'string' ? agent.id : ''
    if (!id) {
      throw new Error('agent_id is required')
    }
    return id
  })
  const agentStates = await Promise.all(
    agentIds.map((agentId) => agentApi.getAgentState(agentId, branchIdValue)),
  )
  const normalizedAgents = agentStates.map((agent) =>
    normalizeAgentState(agent as Record<string, unknown>),
  )
  return { agents: normalizedAgents, convergence: payload.convergence ?? null }
}

const loadSceneContext = async () => {
  const sceneIdValue = sceneId.value
  assertValidSceneId(sceneIdValue)
  assertSceneInProject(sceneIdValue)
  const context = await fetchSceneContext(sceneIdValue, branchId.value)
  const normalized = normalizeSceneContext(context, sceneIdValue)
  sceneContext.value = normalized
  return normalized
}

const loadAgents = async (options: { strict?: boolean } = {}) => {
  if (!hasProjectContext.value) {
    agents.value = []
    convergence.value = null
    agentLoadError.value = null
    agentsLoading.value = false
    if (options.strict) {
      throw new Error('project context is required')
    }
    return []
  }
  agentLoadError.value = null
  convergence.value = null
  agentsLoading.value = true
  try {
    const result = await fetchAgentsPayload()
    agents.value = result.agents
    convergence.value = result.convergence
    return result.agents
  } catch (error) {
    agentLoadError.value = error instanceof Error ? error : new Error('agents load failed')
    agents.value = []
    if (options.strict) {
      throw error
    }
    return []
  } finally {
    agentsLoading.value = false
  }
}

onMounted(() => {
  if (!hasProjectContext.value) {
    return
  }
  void (async () => {
    await loadSceneOptions()
    if (!hasSceneId.value) {
      return
    }
    await loadSceneContext()
    await loadAgents()
  })().catch((error) => {
    sceneListError.value = resolveRequestErrorMessage(error, 'Failed to load scene context.')
  })
})

watch(sceneId, (value) => {
  if (value && value !== selectedSceneId.value) {
    selectedSceneId.value = value
  }
})

const startSimulation = async () => {
  if (!hasSceneId.value) {
    return
  }
  logs.value = [
    {
      id: 'pending',
      time: 'pending',
      text: 'Loading simulations',
    },
  ]
  const sceneIdValue = sceneId.value
  try {
    const configs = (await store.fetchSimulations(sceneIdValue)) as SimulationConfig[]
    rounds.value = configs
    currentRound.value = 1
    logs.value = buildLogs(configs)
  } catch (error) {
    return
  }
}

const stepSimulation = async () => {
  if (!hasSceneId.value) {
    return
  }
  sceneListError.value = ''
  try {
    const context = await loadSceneContext()
    const loadedAgents = await loadAgents({ strict: true })
    const roundId = `round-${logs.value.length + 1}`
    logs.value = [
      ...logs.value,
      {
        id: roundId,
        time: roundId,
        text: `Round ${roundId} executed`,
      },
    ]
    const resultPromise = store.runRound({
      round_id: roundId,
      scene_context: context,
      agents: loadedAgents,
    })
    converged.value = store.status === 'running'
    const result = (await resultPromise) as SimulationRoundResult | { convergence?: boolean }
    if ('round_id' in result) {
      rounds.value = [...rounds.value, result as SimulationRoundResult]
      currentRound.value = rounds.value.length
    }
    const convergenceScore = (result as SimulationRoundResult).convergence_score
    const legacyConvergence = (result as { convergence?: boolean }).convergence
    converged.value =
      typeof convergenceScore === 'number' ? convergenceScore >= 0.8 : Boolean(legacyConvergence)
  } catch (error) {
    sceneListError.value = resolveRequestErrorMessage(error, 'Failed to run simulation step.')
  }
}

const runSceneSimulation = async () => {
  if (!hasSceneId.value) {
    return
  }
  sceneListError.value = ''
  try {
    const context = await loadSceneContext()
    const sceneIdValue = context['scene_id']
    if (typeof sceneIdValue !== 'string' || sceneIdValue.length === 0) {
      return
    }
    logs.value = [
      ...logs.value,
      {
        id: sceneIdValue,
        time: sceneIdValue,
        text: `Scene ${sceneIdValue} executed`,
      },
    ]
    const events = Array.isArray(context['events']) ? context['events'] : []
    const sceneSummary =
      typeof context['summary'] === 'string' ? context['summary'] : ''
    const sceneExpected =
      typeof context['expected_outcome'] === 'string' ? context['expected_outcome'] : ''
    await store.runScene({
      scene_context: {
        ...context,
        scene: context['scene'] ?? {
          scene_id: sceneIdValue,
          summary: sceneSummary,
          expected_outcome: sceneExpected,
        },
        events,
      },
      max_rounds: 1,
    })
  } catch (error) {
    sceneListError.value = resolveRequestErrorMessage(error, 'Failed to run scene simulation.')
  }
}

const stopSimulation = () => {
  store.setStatus('idle')
  converged.value = false
}

const resetSimulation = () => {
  store.reset()
  logs.value = []
  rounds.value = []
  currentRound.value = 1
  converged.value = false
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

.controls {
  display: flex;
  gap: 8px;
}

.run-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
}

.empty-panel {
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  padding: 12px;
}

.full {
  width: 120px;
}

.converged {
  font-weight: 600;
  color: #047857;
}

.log-panel {
  display: grid;
  gap: 6px;
}

.log-line {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.log-time {
  color: #9ca3af;
}

.log-text {
  color: #374151;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}

.scene-select {
  display: grid;
  gap: 8px;
}

.field {
  display: grid;
  gap: 6px;
}

.label {
  font-size: 12px;
  color: #6b7280;
}

select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
}
</style>

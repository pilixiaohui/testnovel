import { defineStore } from 'pinia'
import {
  fetchSnowflakeStep1,
  fetchSnowflakeStep2,
  fetchSnowflakeStep3,
  fetchSnowflakeStep4,
  fetchSnowflakeStep5,
  fetchSnowflakeStep6,
  saveSnowflakeStep,
  snowflakeApi,
} from '../api/snowflake'
import { anchorApi } from '../api/anchor'
import { branchApi } from '../api/branch'
import type {
  SnowflakeAct,
  SnowflakeAnchor,
  SnowflakeChapter,
  SnowflakeCharacter,
  SnowflakeRootState,
  SnowflakeSceneNode,
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakeStep5Payload,
  SnowflakeSteps,
  SnowflakeStructure,
} from '../types/snowflake'

interface SnowflakeStepAliases {
  logline: string[]
  root: SnowflakeStructure | null
  characters: SnowflakeCharacter[]
  scenes: SnowflakeSceneNode[]
  acts: SnowflakeAct[]
  chapters: SnowflakeChapter[]
  anchors: SnowflakeAnchor[]
}

interface SnowflakeState extends SnowflakeRootState, SnowflakeStepAliases {}

type SnowflakePromptOptions = {
  prompt: string
}


type SnowflakeRootSnapshot = {
  root_id: string
  branch_id: string
  logline: string
  theme: string
  ending: string
  characters: SnowflakeCharacter[]
  scenes: SnowflakeSceneNode[]
  three_disasters?: string[]
  created_at?: string
}

const emptySteps: SnowflakeSteps = {
  logline: [],
  root: null,
  characters: [],
  scenes: [],
  acts: [],
  chapters: [],
  anchors: [],
}

const parseJsonPayload = (content: string, label: string) => {
  try {
    return JSON.parse(content) as unknown
  } catch (error) {
    throw new Error(`${label} is required`)
  }
}

const ensureArray = <T,>(value: unknown, label: string): T[] => {
  if (!Array.isArray(value)) {
    throw new Error(`${label} list is required`)
  }
  return value as T[]
}

const ensureObject = (value: unknown, label: string): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} is required`)
  }
  return value as Record<string, unknown>
}

const normalizeRootPayload = (root: SnowflakeStructure): SnowflakeStructure => {
  const disasters = Array.isArray(root.three_disasters)
    ? root.three_disasters.filter((item): item is string => typeof item === 'string')
    : []
  const normalized = [...disasters]
  while (normalized.length < 3) {
    normalized.push('')
  }
  if (normalized.length > 3) {
    normalized.length = 3
  }
  return {
    ...root,
    three_disasters: normalized,
  }
}

const attachStepAliases = (state: SnowflakeRootState): SnowflakeState => {
  Object.defineProperties(state, {
    logline: {
      get: () => state.steps.logline,
      enumerable: false,
    },
    root: {
      get: () => state.steps.root,
      enumerable: false,
    },
    characters: {
      get: () => state.steps.characters,
      enumerable: false,
    },
    scenes: {
      get: () => state.steps.scenes,
      enumerable: false,
    },
    acts: {
      get: () => state.steps.acts,
      enumerable: false,
    },
    chapters: {
      get: () => state.steps.chapters,
      enumerable: false,
    },
    anchors: {
      get: () => state.steps.anchors,
      enumerable: false,
    },
  })

  return state as SnowflakeState
}

const createState = (): SnowflakeState =>
  attachStepAliases({
    id: '',
    created_at: '',
    steps: { ...emptySteps },
  })

export const useSnowflakeStore = defineStore('snowflake', {
  state: (): SnowflakeState => createState(),
  getters: {
    logline: (state: SnowflakeState) => state.steps.logline,
    root: (state: SnowflakeState) => state.steps.root,
    characters: (state: SnowflakeState) => state.steps.characters,
    scenes: (state: SnowflakeState) => state.steps.scenes,
    acts: (state: SnowflakeState) => state.steps.acts,
    chapters: (state: SnowflakeState) => state.steps.chapters,
    anchors: (state: SnowflakeState) => state.steps.anchors,
  },
  actions: {
    setRoot(root: SnowflakeRootState) {
      this.id = root.id
      this.created_at = root.created_at
      this.steps = root.steps
    },
    reset() {
      this.id = ''
      this.created_at = ''
      this.steps = { ...emptySteps }
    },
    updateStepContent(step: number, content: string) {
      if (!Number.isInteger(step) || step < 1 || step > 6) {
        throw new Error('step is required')
      }
      if (step === 1) {
        this.steps.logline = content.split('\n')
        return
      }
      const payload = parseJsonPayload(content, 'step content')
      if (step === 2) {
        const root = ensureObject(payload, 'root') as unknown as SnowflakeStructure
        this.steps.root = root
        const rootId = typeof root.id === 'string' ? root.id : ''
        if (rootId) {
          this.id = rootId
        }
        return
      }
      if (step === 3) {
        this.steps.characters = ensureArray<SnowflakeCharacter>(payload, 'characters')
        return
      }
      if (step === 4) {
        this.steps.scenes = ensureArray<SnowflakeSceneNode>(payload, 'scenes')
        return
      }
      if (step === 5) {
        const record = ensureObject(payload, 'step5 payload')
        this.steps.acts = ensureArray<SnowflakeAct>(record.acts, 'acts')
        this.steps.chapters = ensureArray<SnowflakeChapter>(record.chapters, 'chapters')
        return
      }
      if (step === 6) {
        this.steps.anchors = ensureArray<SnowflakeAnchor>(payload, 'anchors')
        return
      }
    },
    async saveStepToBackend(
      step: 'step1' | 'step2' | 'step3' | 'step4' | 'step5' | 'step6',
      data: Record<string, unknown>,
    ) {
      if (!this.id) {
        throw new Error('root_id is required for saving snowflake step')
      }
      await saveSnowflakeStep({ root_id: this.id, step, data })
    },
    async restoreFromBackend(rootId: string, branchId = 'main') {
      if (!rootId) {
        throw new Error('root_id is required for restoring snowflake state')
      }

      const [rootSnapshot, acts, anchors] = (await Promise.all([
        branchApi.getRootSnapshot(rootId, branchId),
        snowflakeApi.listActs(rootId),
        anchorApi.listAnchors(rootId, branchId),
      ])) as [SnowflakeRootSnapshot, SnowflakeAct[], SnowflakeAnchor[]]

      const chaptersByAct = (await Promise.all(
        acts.map((act) => snowflakeApi.listChapters(act.id)),
      )) as SnowflakeChapter[][]

      const chapters = chaptersByAct.flat()

      const restoredRoot: SnowflakeStructure = {
        id: rootId,
        logline: rootSnapshot.logline,
        theme: rootSnapshot.theme,
        ending: rootSnapshot.ending,
        three_disasters: Array.isArray(rootSnapshot.three_disasters)
          ? rootSnapshot.three_disasters
          : [],
        created_at: rootSnapshot.created_at,
      }

      const steps: SnowflakeSteps = {
        ...emptySteps,
        logline: rootSnapshot.logline ? [rootSnapshot.logline] : [],
        root: restoredRoot,
        characters: rootSnapshot.characters,
        scenes: rootSnapshot.scenes,
        acts,
        chapters,
        anchors,
      }

      this.id = rootId
      this.created_at = rootSnapshot.created_at as SnowflakeRootState['created_at']
      this.steps = steps

      const step = anchors.length
        ? 6
        : chapters.length || acts.length
          ? 5
          : rootSnapshot.scenes.length
            ? 4
            : rootSnapshot.characters.length
              ? 3
              : rootSnapshot.logline || rootSnapshot.theme || rootSnapshot.ending
                ? 2
                : 1

      return { step }
    },
    async loadProgress(rootId: string, branchId = 'main') {
      return this.restoreFromBackend(rootId, branchId)
    },
    async fetchStep1(idea: string, options?: SnowflakePromptOptions) {
      const request = options ? fetchSnowflakeStep1(idea, options) : fetchSnowflakeStep1(idea)
      const logline = (await request) as unknown as string[]
      this.steps.logline = logline
      if (this.id) {
        await this.saveStepToBackend('step1', { logline })
      }
      return logline
    },
    async fetchStep2(logline: string, options?: SnowflakePromptOptions) {
      const request = options ? fetchSnowflakeStep2(logline, options) : fetchSnowflakeStep2(logline)
      const root = (await request) as unknown as SnowflakeStructure
      const normalizedRoot = normalizeRootPayload(root)
      this.steps.root = normalizedRoot
      const trimmedLogline = logline.trim()
      if (trimmedLogline && this.steps.logline.length === 0) {
        this.steps.logline = [trimmedLogline]
      }
      if (normalizedRoot.id && !this.id) {
        this.id = normalizedRoot.id
      }
      if (this.id) {
        await this.saveStepToBackend('step2', { root: normalizedRoot })
      }
      return normalizedRoot
    },
    async fetchStep3(root: SnowflakeStructure, options?: SnowflakePromptOptions) {
      const request = options ? fetchSnowflakeStep3(root, options) : fetchSnowflakeStep3(root)
      const characters = (await request) as unknown as SnowflakeCharacter[]
      this.steps.characters = characters
      if (this.id) {
        await this.saveStepToBackend('step3', { characters })
      }
      return characters
    },
    async fetchStep4(payload: SnowflakeStep4Payload, options?: SnowflakePromptOptions) {
      const normalizedRoot = normalizeRootPayload(payload.root)
      const normalizedPayload = { ...payload, root: normalizedRoot }
      const request = options
        ? fetchSnowflakeStep4(normalizedPayload, options)
        : fetchSnowflakeStep4(normalizedPayload)
      const result = (await request) as unknown as SnowflakeStep4Result
      this.steps.scenes = result.scenes
      this.id = result.root_id
      if (this.steps.logline.length === 0) {
        const derivedLogline = normalizedRoot.logline.trim()
        if (derivedLogline) {
          this.steps.logline = [derivedLogline]
        }
      }
      if (this.steps.logline.length > 0) {
        await this.saveStepToBackend('step1', { logline: [...this.steps.logline] })
      }
      await this.saveStepToBackend('step2', { root: normalizedRoot })
      await this.saveStepToBackend('step3', { characters: normalizedPayload.characters })
      await this.saveStepToBackend('step4', {
        root: normalizedRoot,
        characters: normalizedPayload.characters,
        scenes: result.scenes,
      })
      return result
    },
    async fetchStep5(payload: SnowflakeStep5Payload, options?: SnowflakePromptOptions) {
      const normalizedRoot = normalizeRootPayload(payload.root)
      const normalizedPayload = { ...payload, root: normalizedRoot }
      const acts = (await (options
        ? fetchSnowflakeStep5(normalizedPayload, options)
        : fetchSnowflakeStep5(normalizedPayload))) as unknown as SnowflakeAct[]
      const chapters = (await (options
        ? fetchSnowflakeStep6(normalizedPayload, options)
        : fetchSnowflakeStep6(normalizedPayload))) as unknown as SnowflakeChapter[]
      this.id = normalizedPayload.root_id
      this.steps.acts = acts
      this.steps.chapters = chapters
      await this.saveStepToBackend('step5', {
        acts,
        chapters,
      })
      return { acts, chapters }
    },
    async fetchStep6(branchId = 'main', options?: SnowflakePromptOptions) {
      if (!this.id) {
        throw new Error('root_id is required for anchors')
      }
      const root = this.steps.root
      if (!root) {
        throw new Error('root is required for anchors')
      }
      const normalizedRoot = normalizeRootPayload(root)
      this.steps.root = normalizedRoot
      const anchors = (await anchorApi.generateAnchors(
        this.id,
        branchId,
        normalizedRoot,
        this.steps.characters,
        options,
      )) as unknown as SnowflakeAnchor[]
      this.steps.anchors = anchors
      await this.saveStepToBackend('step6', { anchors })
      return anchors
    },
  },
})

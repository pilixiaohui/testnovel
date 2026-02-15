import { apiClient } from './index'
import type {
  SnowflakeAct,
  SnowflakeChapter,
  SnowflakeCharacter,
  SnowflakeRoot,
  SnowflakePromptSet,
  SnowflakeStep4Payload,
  SnowflakeStep4Result,
  SnowflakeStep5Payload,
  SnowflakeStructure,
  SnowflakeSceneNode,
} from '../types/snowflake'

type SnowflakeRootPayload = SnowflakeStructure | SnowflakeRoot

type SnowflakePromptOptions = {
  prompt: string
}

type SaveSnowflakeStepPayload = {
  root_id: string
  step: 'step1' | 'step2' | 'step3' | 'step4' | 'step5' | 'step6'
  data: Record<string, unknown>
}

const generateLoglinesRequest = (idea: string, options?: SnowflakePromptOptions) =>
  apiClient.post<string[]>('/snowflake/step1', options ? { idea, prompt: options.prompt } : { idea })

const generateStructureRequest = (logline: string, options?: SnowflakePromptOptions) =>
  apiClient.post<SnowflakeRoot>('/snowflake/step2', options ? { logline, prompt: options.prompt } : { logline })

const generateCharactersRequest = (root: SnowflakeRootPayload, options?: SnowflakePromptOptions) =>
  apiClient.post<SnowflakeCharacter[]>('/snowflake/step3', options ? { ...root, prompt: options.prompt } : root)

const generateScenesRequest = (
  root: SnowflakeRootPayload,
  characters: SnowflakeCharacter[],
  options?: SnowflakePromptOptions,
) =>
  apiClient.post<SnowflakeStep4Result>(
    '/snowflake/step4',
    options ? { root, characters, prompt: options.prompt } : { root, characters },
  )

const generateActsRequest = (
  rootId: string,
  root: SnowflakeRootPayload,
  characters: SnowflakeCharacter[],
  options?: SnowflakePromptOptions,
) =>
  apiClient.post<SnowflakeAct[]>(
    '/snowflake/step5a',
    options ? { root_id: rootId, root, characters, prompt: options.prompt } : { root_id: rootId, root, characters },
  )

const generateChaptersRequest = (
  rootId: string,
  root: SnowflakeRootPayload,
  characters: SnowflakeCharacter[],
  options?: SnowflakePromptOptions,
) =>
  apiClient.post<SnowflakeChapter[]>(
    '/snowflake/step5b',
    options ? { root_id: rootId, root, characters, prompt: options.prompt } : { root_id: rootId, root, characters },
  )

const listActsRequest = (rootId: string) => apiClient.get<SnowflakeAct[]>(`/roots/${rootId}/acts`)

const listChaptersRequest = (actId: string) =>
  apiClient.get<SnowflakeChapter[]>(`/acts/${actId}/chapters`)


const saveSnowflakeStepRequest = (payload: SaveSnowflakeStepPayload) =>
  apiClient.post(`/roots/${payload.root_id}/snowflake/steps`, {
    step: payload.step,
    data: payload.data,
  })


export const snowflakeApi = {
  generateLoglines: generateLoglinesRequest,
  generateStructure: generateStructureRequest,
  generateCharacters: generateCharactersRequest,
  generateScenes: generateScenesRequest,
  generateActs: generateActsRequest,
  generateChapters: generateChaptersRequest,
  listActs: listActsRequest,
  listChapters: listChaptersRequest,
}

export const fetchSnowflakeStep1 = (idea: string, options?: SnowflakePromptOptions) =>
  generateLoglinesRequest(idea, options)

export const fetchSnowflakeStep2 = (logline: string, options?: SnowflakePromptOptions) =>
  generateStructureRequest(logline, options)

export const fetchSnowflakeRoot = (logline: string) => generateStructureRequest(logline)

export const fetchSnowflakeStep3 = (root: SnowflakeStructure, options?: SnowflakePromptOptions) =>
  generateCharactersRequest(root, options)

export const fetchSnowflakeStep4 = (
  payload: SnowflakeStep4Payload,
  options?: SnowflakePromptOptions,
) => generateScenesRequest(payload.root, payload.characters, options)

export const fetchSnowflakeStep5 = (
  payload: SnowflakeStep5Payload,
  options?: SnowflakePromptOptions,
) => generateActsRequest(payload.root_id, payload.root, payload.characters, options)

export const fetchSnowflakeStep6 = (
  payload: SnowflakeStep5Payload,
  options?: SnowflakePromptOptions,
) => generateChaptersRequest(payload.root_id, payload.root, payload.characters, options)


export const saveSnowflakeStep = (payload: SaveSnowflakeStepPayload) =>
  saveSnowflakeStepRequest(payload)

export const fetchSnowflakePrompts = (rootId: string, branchId: string) =>
  apiClient.get<SnowflakePromptSet>(`/roots/${rootId}/snowflake/prompts`, {
    params: { branch_id: branchId },
  })

export const saveSnowflakePrompts = (
  rootId: string,
  branchId: string,
  prompts: SnowflakePromptSet,
) =>
  apiClient.put(`/roots/${rootId}/snowflake/prompts`, prompts, {
    params: { branch_id: branchId },
  })

export const resetSnowflakePrompts = (rootId: string, branchId: string) =>
  apiClient.post<SnowflakePromptSet>(
    `/roots/${rootId}/snowflake/prompts/reset`,
    {},
    { params: { branch_id: branchId } },
  )

export const updateSnowflakeLogline = (rootId: string, loglines: string[]) =>
  apiClient.post(`/roots/${rootId}/snowflake/steps`, {
    step: 'step1',
    data: { logline: loglines },
  })

export const updateSnowflakeCharacter = (
  rootId: string,
  branchId: string,
  characterId: string,
  payload: Partial<SnowflakeCharacter>,
) =>
  apiClient.put(`/roots/${rootId}/entities/${characterId}`, payload, {
    params: { branch_id: branchId },
  })

export const updateSnowflakeAct = (actId: string, payload: Partial<SnowflakeAct>) =>
  apiClient.put(`/acts/${actId}`, payload)

export const updateSnowflakeChapter = (chapterId: string, payload: Partial<SnowflakeChapter>) =>
  apiClient.put(`/chapters/${chapterId}`, payload)

export const updateSnowflakeScene = (sceneId: string, payload: Partial<SnowflakeSceneNode>) =>
  apiClient.put(`/scenes/${sceneId}`, payload)

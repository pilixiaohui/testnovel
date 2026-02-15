import { apiClient } from './index'

export type LlmSettingsPayload = {
  llm_config: {
    model: string
    temperature: number
    max_tokens: number
    timeout: number
    system_instruction: string
  }
  system_config: {
    auto_save: boolean
    ui_density: 'comfortable' | 'compact' | 'spacious'
  }
}

const toponeGenerateRequest = (data: Record<string, unknown>) =>
  apiClient.post('/llm/topone/generate', data)

const logicCheckRequest = (data: Record<string, unknown>) => apiClient.post('/logic/check', data)

const stateExtractRequest = (data: Record<string, unknown>) => apiClient.post('/state/extract', data)

const stateCommitRequest = (rootId: string, branchId: string, proposals: unknown[]) =>
  apiClient.post('/state/commit', proposals, {
    params: {
      root_id: rootId,
      branch_id: branchId,
    },
  })

const fetchLlmSettingsRequest = () => apiClient.get<LlmSettingsPayload>('/settings/llm')

const saveLlmSettingsRequest = (payload: LlmSettingsPayload) =>
  apiClient.put<LlmSettingsPayload>('/settings/llm', payload)

export const llmApi = {
  toponeGenerate: toponeGenerateRequest,
  logicCheck: logicCheckRequest,
  stateExtract: stateExtractRequest,
  stateCommit: stateCommitRequest,
}

export const fetchLlmStatus = () => apiClient.get('/llm/status')

export const fetchLlmSettings = () => fetchLlmSettingsRequest()

export const saveLlmSettings = (payload: LlmSettingsPayload) => saveLlmSettingsRequest(payload)

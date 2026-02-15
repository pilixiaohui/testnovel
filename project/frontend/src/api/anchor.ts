import { apiClient } from './index'
import type { SnowflakeAnchor, SnowflakeCharacter, SnowflakeRoot, SnowflakeStructure } from '../types/snowflake'

type AnchorCheckResult = {
  id: string
  reachable: boolean
  missing_conditions: string[]
  achieved: boolean
}

type AnchorRootPayload = SnowflakeStructure | SnowflakeRoot

type AnchorPromptOptions = {
  prompt: string
}

const generateAnchorsRequest = (
  rootId: string,
  branchId: string,
  root: AnchorRootPayload,
  characters: SnowflakeCharacter[],
  options?: AnchorPromptOptions,
) =>
  apiClient.post<SnowflakeAnchor[]>(
    `/roots/${rootId}/anchors`,
    options
      ? { branch_id: branchId, root, characters, prompt: options.prompt }
      : { branch_id: branchId, root, characters },
  )

const listAnchorsRequest = (rootId: string, branchId: string) =>
  apiClient.get<SnowflakeAnchor[]>(`/roots/${rootId}/anchors`, {
    params: { branch_id: branchId },
  })

const updateAnchorRequest = (id: string, data: Partial<SnowflakeAnchor>) =>
  apiClient.put<SnowflakeAnchor>(`/anchors/${id}`, data)

const checkAnchorRequest = (
  id: string,
  worldState: Record<string, unknown>,
  sceneVersionId?: string,
) =>
  apiClient.post<AnchorCheckResult>(`/anchors/${id}/check`, {
    world_state: worldState,
    scene_version_id: sceneVersionId,
  })

export const anchorApi = {
  generateAnchors: generateAnchorsRequest,
  listAnchors: listAnchorsRequest,
  updateAnchor: updateAnchorRequest,
  checkAnchor: checkAnchorRequest,
}

export const fetchAnchors = (
  rootId: string,
  branchId: string,
  root?: AnchorRootPayload,
  characters?: SnowflakeCharacter[],
  options?: AnchorPromptOptions,
) => {
  if (root && characters) {
    return generateAnchorsRequest(rootId, branchId, root, characters, options)
  }
  return listAnchorsRequest(rootId, branchId)
}

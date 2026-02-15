import { apiClient } from './index'

const createSceneRequest = (rootId: string, branchId: string, data: Record<string, unknown>) =>
  apiClient.post(`/roots/${rootId}/scene_origins`, data, {
    params: { branch_id: branchId },
  })

const deleteSceneRequest = (rootId: string, branchId: string, sceneId: string, message: string) =>
  apiClient.post(
    `/roots/${rootId}/scenes/${sceneId}/delete`,
    { message },
    { params: { branch_id: branchId } },
  )

const completeSceneRequest = (
  sceneId: string,
  branchId: string,
  actualOutcome: string,
  summary: string,
) =>
  apiClient.post(
    `/scenes/${sceneId}/complete`,
    {
      actual_outcome: actualOutcome,
      summary,
    },
    { params: { branch_id: branchId } },
  )

const completeOrchestratedRequest = (sceneId: string, data: Record<string, unknown>) =>
  apiClient.post(`/scenes/${sceneId}/complete/orchestrated`, data)

const renderSceneRequest = (sceneId: string, branchId: string, payload: Record<string, unknown>) =>
  apiClient.post(`/scenes/${sceneId}/render`, payload, {
    params: { branch_id: branchId },
  })

const getContextRequest = (sceneId: string, branchId: string) =>
  apiClient.get(`/scenes/${sceneId}/context`, {
    params: { branch_id: branchId },
  })

const diffSceneRequest = (
  sceneId: string,
  branchId: string,
  fromCommitId: string,
  toCommitId: string,
) =>
  apiClient.get(`/scenes/${sceneId}/diff`, {
    params: {
      branch_id: branchId,
      from_commit_id: fromCommitId,
      to_commit_id: toCommitId,
    },
  })

const markDirtyRequest = (sceneId: string, branchId: string) =>
  apiClient.post(`/scenes/${sceneId}/dirty`, null, {
    params: { branch_id: branchId },
  })

const listDirtyScenesRequest = (rootId: string, branchId: string) =>
  apiClient.get(`/roots/${rootId}/dirty_scenes`, {
    params: { branch_id: branchId },
  })

export const sceneApi = {
  createScene: createSceneRequest,
  deleteScene: deleteSceneRequest,
  completeScene: completeSceneRequest,
  completeOrchestrated: completeOrchestratedRequest,
  renderScene: renderSceneRequest,
  getContext: getContextRequest,
  diffScene: diffSceneRequest,
  markDirty: markDirtyRequest,
  listDirtyScenes: listDirtyScenesRequest,
}

export const fetchScenes = (rootId: string, branchId: string) =>
  apiClient.get(`/roots/${rootId}`, {
    params: { branch_id: branchId },
  })

export const fetchSceneContext = (sceneId: string, branchId: string) =>
  apiClient.get(`/scenes/${sceneId}/context`, {
    params: { branch_id: branchId },
  })

export const renderScene = (
  sceneId: string,
  branchId: string,
  payload: Record<string, unknown>,
) => renderSceneRequest(sceneId, branchId, payload)

export const updateScene = (
  sceneId: string,
  branchId: string,
  payload: { outcome: string; summary: string },
) => completeSceneRequest(sceneId, branchId, payload.outcome, payload.summary)

export const diffScene = (
  sceneId: string,
  branchId: string,
  fromCommitId: string,
  toCommitId: string,
) =>
  apiClient.get(`/scenes/${sceneId}/diff`, {
    params: {
      branch_id: branchId,
      from_commit_id: fromCommitId,
      to_commit_id: toCommitId,
    },
  })

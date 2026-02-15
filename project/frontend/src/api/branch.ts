import { apiClient } from './index'

const createBranchRequest = (rootId: string, branchId: string) =>
  apiClient.post(`/roots/${rootId}/branches`, { branch_id: branchId })

const listBranchesRequest = (rootId: string) => apiClient.get<string[]>(`/roots/${rootId}/branches`)

const switchBranchRequest = (rootId: string, branchId: string) =>
  apiClient.post(`/roots/${rootId}/branches/${branchId}/switch`)

const mergeBranchRequest = (rootId: string, branchId: string) =>
  apiClient.post(`/roots/${rootId}/branches/${branchId}/merge`)

const revertBranchRequest = (rootId: string, branchId: string) =>
  apiClient.post(`/roots/${rootId}/branches/${branchId}/revert`)

const forkFromCommitRequest = (rootId: string, sourceCommitId: string, newBranchId: string) =>
  apiClient.post(`/roots/${rootId}/branches/fork_from_commit`, {
    source_commit_id: sourceCommitId,
    new_branch_id: newBranchId,
  })

const forkFromSceneRequest = (
  rootId: string,
  sceneOriginId: string,
  newBranchId: string,
  sourceBranchId: string,
) =>
  apiClient.post(`/roots/${rootId}/branches/fork_from_scene`, {
    scene_origin_id: sceneOriginId,
    new_branch_id: newBranchId,
    source_branch_id: sourceBranchId,
  })

const resetBranchRequest = (rootId: string, branchId: string, commitId: string) =>
  apiClient.post(`/roots/${rootId}/branches/${branchId}/reset`, {
    commit_id: commitId,
  })

const getBranchHistoryRequest = (rootId: string, branchId: string) =>
  apiClient.get(`/roots/${rootId}/branches/${branchId}/history`)

const getRootSnapshotRequest = (rootId: string, branchId: string) =>
  apiClient.get(`/roots/${rootId}`, {
    params: { branch_id: branchId },
  })

export const branchApi = {
  createBranch: createBranchRequest,
  listBranches: listBranchesRequest,
  switchBranch: switchBranchRequest,
  mergeBranch: mergeBranchRequest,
  revertBranch: revertBranchRequest,
  forkFromCommit: forkFromCommitRequest,
  forkFromScene: forkFromSceneRequest,
  resetBranch: resetBranchRequest,
  getBranchHistory: getBranchHistoryRequest,
  getRootSnapshot: getRootSnapshotRequest,
}

export const fetchBranches = () => apiClient.get('/branches')

import { apiClient } from './index'

const commitSceneRequest = (rootId: string, branchId: string, data: Record<string, unknown>) =>
  apiClient.post(`/roots/${rootId}/branches/${branchId}/commit`, data)

const gcCommitsRequest = (rootId: string, options?: Record<string, unknown>) =>
  apiClient.post('/commits/gc', {
    root_id: rootId,
    ...options,
  })

export const commitApi = {
  commitScene: commitSceneRequest,
  gcCommits: gcCommitsRequest,
}

export const fetchCommits = () => apiClient.get('/commits')

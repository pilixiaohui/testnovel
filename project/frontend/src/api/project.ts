import { apiClient } from '@/api/index'
import type { ProjectDeleteResponse, ProjectDetailPayload, ProjectListResponse, ProjectSummary } from '@/types/project'

export const fetchProjects = (): Promise<ProjectListResponse> => apiClient.get<ProjectListResponse>('/roots')

export const fetchProject = (
  rootId: string,
  branchId = 'main',
): Promise<ProjectDetailPayload> =>
  apiClient.get<ProjectDetailPayload>(`/roots/${rootId}`, {
    params: { branch_id: branchId },
  })

export const createProject = (name: string): Promise<ProjectSummary> =>
  apiClient.post<ProjectSummary>('/roots', { name })

export const deleteProject = (rootId: string): Promise<ProjectDeleteResponse> =>
  apiClient.delete<ProjectDeleteResponse>(`/roots/${rootId}`)

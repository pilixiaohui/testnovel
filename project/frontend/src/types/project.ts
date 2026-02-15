import type { ApiResponse } from './api'

export interface ProjectSummary {
  root_id: string
  name: string
  logline?: string
  created_at: string
  updated_at: string
}

export type ProjectDetail = {
  root_id?: string
  branch_id?: string
  scene_id?: string
  name?: string
  logline?: string
  created_at?: string
  updated_at?: string
}

export type ProjectDetailPayload = ProjectDetail | ApiResponse<ProjectDetail>

export type ProjectListResponse = {
  roots: ProjectSummary[]
}

export type ProjectDeleteResponse = {
  success: boolean
}

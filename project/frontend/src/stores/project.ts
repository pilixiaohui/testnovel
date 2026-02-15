import { defineStore } from 'pinia'
import { createProject, deleteProject as deleteProjectRequest, fetchProject, fetchProjects } from '@/api/project'
import { commitApi } from '@/api/commit'
import { branchApi } from '@/api/branch'
import type { ProjectDetailPayload, ProjectSummary } from '@/types/project'

export type { ProjectSummary } from '@/types/project'

const ROOT_ID_STORAGE_KEY = 'project_root_id'
const BRANCH_ID_STORAGE_KEY = 'project_branch_id'
const SCENE_ID_STORAGE_KEY = 'project_scene_id'
const DEFAULT_BRANCH_ID = 'main'
const PROJECT_NAME_MAX_LENGTH = 255

interface ProjectState {
  root_id: string
  branch_id: string
  scene_id: string
  branches: string[]
  projects: ProjectSummary[]
  is_loading: boolean
  api_error: string
  project_list_error: string | null
  project_list_timeout: boolean
}

type RouteContext = {
  name?: string
  params: Record<string, string | undefined>
  query: Record<string, string | undefined>
}

const getInitialRootId = () => localStorage.getItem(ROOT_ID_STORAGE_KEY) || ''
const getInitialBranchId = () => localStorage.getItem(BRANCH_ID_STORAGE_KEY) || DEFAULT_BRANCH_ID
const getInitialSceneId = () => localStorage.getItem(SCENE_ID_STORAGE_KEY) || ''

const persistProjectIds = (rootId: string, branchId: string, sceneId: string) => {
  localStorage.setItem(ROOT_ID_STORAGE_KEY, rootId)
  localStorage.setItem(BRANCH_ID_STORAGE_KEY, branchId)
  localStorage.setItem(SCENE_ID_STORAGE_KEY, sceneId)
}

const clearProjectStorage = () => {
  localStorage.removeItem(ROOT_ID_STORAGE_KEY)
  localStorage.removeItem(BRANCH_ID_STORAGE_KEY)
  localStorage.removeItem(SCENE_ID_STORAGE_KEY)
}

const resolveProjectDetail = (payload: ProjectDetailPayload, fallbackRootId: string) => {
  if (!payload || typeof payload !== 'object') {
    throw new Error('project payload is required')
  }
  const normalized = (payload as { data?: unknown }).data ?? payload
  if (!normalized || typeof normalized !== 'object') {
    throw new Error('project payload is required')
  }
  const detail = normalized as { root_id?: string; branch_id?: string; scene_id?: string }
  const rootId = typeof detail.root_id === 'string' && detail.root_id ? detail.root_id : fallbackRootId
  const branchId =
    typeof detail.branch_id === 'string' && detail.branch_id.trim().length > 0
      ? detail.branch_id
      : DEFAULT_BRANCH_ID
  const sceneId = typeof detail.scene_id === 'string' ? detail.scene_id : ''
  return { rootId, branchId, sceneId }
}

export const useProjectStore = defineStore('project', {
  state: (): ProjectState => ({
    root_id: getInitialRootId(),
    branch_id: getInitialBranchId(),
    scene_id: getInitialSceneId(),
    branches: [],
    projects: [],
    is_loading: false,
    api_error: '',
    project_list_error: null,
    project_list_timeout: false,
  }),
  actions: {
    async listProjects() {
      this.project_list_error = null
      this.project_list_timeout = false
      this.api_error = ''
      this.setLoading(true)
      try {
        const response = await fetchProjects()
        this.projects = response.roots
        if (this.root_id && !this.projects.some((project) => project.root_id === this.root_id)) {
          this.clearProject()
        }
      } catch (error) {
        if (error instanceof Error) {
          this.project_list_error = error.message
          this.project_list_timeout = error.message === 'timeout'
          this.api_error = error.message
        } else {
          this.api_error = 'Failed to load projects.'
        }
        throw error
      } finally {
        this.setLoading(false)
      }
    },
    setLoading(loading: boolean) {
      this.is_loading = loading
    },
    setProject(rootId: string, branchId = DEFAULT_BRANCH_ID, sceneId = '') {
      this.root_id = rootId
      this.branch_id = branchId
      this.scene_id = sceneId
      this.saveToLocalStorage()
    },
    saveToLocalStorage() {
      persistProjectIds(this.root_id, this.branch_id, this.scene_id)
    },
    restoreFromLocalStorage() {
      this.root_id = getInitialRootId()
      this.branch_id = getInitialBranchId()
      this.scene_id = getInitialSceneId()
    },
    clearProject() {
      this.root_id = ''
      this.branch_id = DEFAULT_BRANCH_ID
      this.scene_id = ''
      this.branches = []
      clearProjectStorage()
    },
    setCurrentProject(rootId: string, branchId: string, sceneId: string) {
      this.setProject(rootId, branchId, sceneId)
    },
    async loadBranches(rootId: string) {
      if (!rootId) {
        throw new Error('root_id is required')
      }
      const branches = (await branchApi.listBranches(rootId)) as string[]
      this.branches = branches
      return branches
    },
    async createBranch(rootId: string, branchId: string) {
      if (!rootId || !branchId) {
        throw new Error('root_id and branch_id are required')
      }
      const response = (await branchApi.createBranch(rootId, branchId)) as {
        root_id?: string
        branch_id?: string
      }
      const nextBranchId = response.branch_id
      if (!nextBranchId) {
        throw new Error('branch_id is required')
      }
      this.branch_id = nextBranchId
      if (!this.branches.includes(nextBranchId)) {
        this.branches = [...this.branches, nextBranchId]
      }
      localStorage.setItem(BRANCH_ID_STORAGE_KEY, nextBranchId)
      return response
    },
    async switchBranch(rootId: string, branchId: string) {
      if (!rootId || !branchId) {
        throw new Error('root_id and branch_id are required')
      }
      const response = (await branchApi.switchBranch(rootId, branchId)) as {
        root_id?: string
        branch_id?: string
      }
      const nextBranchId = response.branch_id
      if (!nextBranchId) {
        throw new Error('branch_id is required')
      }
      this.branch_id = nextBranchId
      localStorage.setItem(BRANCH_ID_STORAGE_KEY, nextBranchId)
      return response
    },
    async deleteProject(rootId: string) {
      if (!rootId) {
        throw new Error('root_id is required')
      }
      await deleteProjectRequest(rootId)
      this.projects = this.projects.filter((project) => project.root_id !== rootId)
      if (this.root_id === rootId) {
        this.clearProject()
      }
    },
    async syncFromRoute(route: RouteContext) {
      const sceneId = route.params.sceneId

      const rootId = route.query.root_id ?? route.params.rootId
      const branchId = route.query.branch_id ?? route.params.branchId

      if (rootId) {
        this.root_id = rootId
        localStorage.setItem(ROOT_ID_STORAGE_KEY, rootId)
      }
      if (branchId) {
        this.branch_id = branchId
        localStorage.setItem(BRANCH_ID_STORAGE_KEY, branchId)
      }
      if (sceneId) {
        this.scene_id = sceneId
        localStorage.setItem(SCENE_ID_STORAGE_KEY, sceneId)
      }
    },
    async loadProject(rootId: string) {
      if (!rootId) {
        throw new Error('root_id is required')
      }
      const payload = await fetchProject(rootId, this.branch_id || DEFAULT_BRANCH_ID)
      const resolved = resolveProjectDetail(payload, rootId)
      this.setProject(resolved.rootId, resolved.branchId, resolved.sceneId)
      return payload
    },
    async saveProjectData(rootId: string, content: Record<string, unknown>) {
      if (!rootId) {
        throw new Error('root_id is required')
      }
      const branchId = this.branch_id
      if (!branchId) {
        throw new Error('branch_id is required')
      }
      const sceneId = this.scene_id
      if (!sceneId) {
        throw new Error('scene_id is required')
      }
      if (!content || Object.keys(content).length === 0) {
        throw new Error('content is required')
      }
      this.api_error = ''
      this.setLoading(true)
      try {
        return await commitApi.commitScene(rootId, branchId, {
          scene_origin_id: sceneId,
          content,
          message: 'Saved project data',
        })
      } catch (error) {
        if (error instanceof Error) {
          this.api_error = error.message
        } else {
          this.api_error = 'Failed to save project data.'
        }
        throw error
      } finally {
        this.setLoading(false)
      }
    },
    async saveProject(payload: { name: string }) {
      const name = payload.name
      if (name.length === 0) {
        throw new Error('Project name is required')
      }
      if (name.length > PROJECT_NAME_MAX_LENGTH) {
        throw new Error('Project name is too long')
      }
      const createdProject = await createProject(name)
      this.projects = [...this.projects, createdProject]
      return createdProject
    },

  },
})

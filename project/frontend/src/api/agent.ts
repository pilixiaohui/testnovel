import { apiClient } from './index'
import type { AgentAction } from '../types/simulation'

const initAgentRequest = (
  entityId: string,
  branchId: string,
  initialDesires: Record<string, unknown>[],
) =>
  apiClient.post(`/entities/${entityId}/agent/init`, {
    branch_id: branchId,
    initial_desires: initialDesires,
  })

const getAgentStateRequest = (entityId: string, branchId: string) =>
  apiClient.get(`/entities/${entityId}/agent/state`, {
    params: { branch_id: branchId },
  })

const updateDesiresRequest = (
  entityId: string,
  branchId: string,
  desires: Record<string, unknown>[],
) =>
  apiClient.put(`/entities/${entityId}/agent/desires`, {
    branch_id: branchId,
    desires,
  })

const decideRequest = (entityId: string, sceneContext: Record<string, unknown>) =>
  apiClient.post<AgentAction>(`/entities/${entityId}/agent/decide`, {
    scene_context: sceneContext,
  })

export const agentApi = {
  initAgent: initAgentRequest,
  getAgentState: getAgentStateRequest,
  updateDesires: updateDesiresRequest,
  decide: decideRequest,
}

export const fetchAgents = () => apiClient.get('/agents')

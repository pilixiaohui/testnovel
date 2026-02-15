import { apiClient } from './index'
import type { SimulationConfig } from '../types/simulation'

const runRoundRequest = (
  sceneContext: Record<string, unknown>,
  agents: Record<string, unknown>[],
  roundId: string,
) =>
  apiClient.post('/simulation/round', {
    scene_context: sceneContext,
    agents,
    round_id: roundId,
  })

const runSceneRequest = (sceneContext: Record<string, unknown>, maxRounds: number) =>
  apiClient.post('/simulation/scene', {
    scene_context: sceneContext,
    max_rounds: maxRounds,
  })

const getLogsRequest = (sceneId: string) =>
  apiClient.get<SimulationConfig[]>(`/simulation/logs/${sceneId}`)

const getSimulationAgentsRequest = (rootId: string, branchId: string) =>
  apiClient.get('/simulation/agents', {
    params: { root_id: rootId, branch_id: branchId },
  })

const renderSceneRequest = (rounds: SimulationConfig[], scene: Record<string, unknown>) =>
  apiClient.post<{ content: string }>('/render/scene', { rounds, scene })

const feedbackLoopRequest = (sceneContext: Record<string, unknown>, rounds: SimulationConfig[]) =>
  apiClient.post('/simulation/feedback', { scene_context: sceneContext, rounds })

export const simulationApi = {
  runRound: runRoundRequest,
  runScene: runSceneRequest,
  getLogs: getLogsRequest,
  getAgents: getSimulationAgentsRequest,
  renderScene: renderSceneRequest,
  feedbackLoop: feedbackLoopRequest,
}

export const fetchSimulationAgents = (rootId: string, branchId: string) =>
  getSimulationAgentsRequest(rootId, branchId)

export const fetchSimulations = (sceneId: string) => getLogsRequest(sceneId)

export const runRound = (payload: Record<string, unknown>) => apiClient.post('/simulation/round', payload)

export const runScene = (payload: Record<string, unknown>) => apiClient.post('/simulation/scene', payload)

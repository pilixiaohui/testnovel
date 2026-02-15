import { apiClient } from './index'
import type { DMArbitration } from '../types/simulation'

const resolveWorldState = (value: Record<string, unknown> | undefined) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value
  }
  return {}
}

const arbitrateRequest = (
  roundId: string,
  actions: Record<string, unknown>[],
  worldState: Record<string, unknown> | undefined,
) =>
  apiClient.post<DMArbitration>('/dm/arbitrate', {
    round_id: roundId,
    actions,
    world_state: resolveWorldState(worldState),
  })

const checkConvergenceRequest = (
  worldState: Record<string, unknown> | undefined,
  nextAnchor: Record<string, unknown>,
) =>
  apiClient.post('/dm/converge', {
    world_state: resolveWorldState(worldState),
    next_anchor: nextAnchor,
  })

const interveneRequest = (
  check: Record<string, unknown>,
  worldState: Record<string, unknown> | undefined,
) =>
  apiClient.post('/dm/intervene', {
    check,
    world_state: resolveWorldState(worldState),
  })

const replanRequest = (
  currentScene: Record<string, unknown>,
  targetAnchor: Record<string, unknown>,
  worldState: Record<string, unknown> | undefined,
) =>
  apiClient.post('/dm/replan', {
    current_scene: currentScene,
    target_anchor: targetAnchor,
    world_state: resolveWorldState(worldState),
  })

export const dmApi = {
  arbitrate: arbitrateRequest,
  checkConvergence: checkConvergenceRequest,
  intervene: interveneRequest,
  replan: replanRequest,
}

export const fetchDmOverview = () => apiClient.get('/dm')

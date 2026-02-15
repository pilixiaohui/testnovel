import type { SimulationConfig } from '../types/simulation'
import { apiClient } from './index'

type FeedbackPayload = {
  scene_context: Record<string, unknown>
  rounds: SimulationConfig[]
}

const feedbackLoopRequest = (sceneContext: Record<string, unknown>, rounds: SimulationConfig[]) =>
  apiClient.post('/simulation/feedback', {
    scene_context: sceneContext,
    rounds,
  })

export const feedbackApi = {
  feedbackLoop: feedbackLoopRequest,
}

export const createFeedback = (payload: FeedbackPayload) =>
  feedbackLoopRequest(payload.scene_context, payload.rounds)

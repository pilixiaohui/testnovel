export interface Desire {
  id: string
  type: 'short_term' | 'long_term' | 'reactive'
  description: string
  priority: number
  satisfaction_condition: string
  created_at_scene: number
  expires_at_scene?: number
}

export interface Intention {
  id: string
  desire_id: string
  action_type: 'attack' | 'flee' | 'negotiate' | 'investigate' | 'wait' | 'other'
  target: string
  expected_outcome: string
  risk_assessment: number
}

export interface AgentAction {
  agent_id: string
  internal_thought: string
  action_type: string
  action_target: string
  dialogue?: string
  action_description: string
}

export interface CharacterAgentState {
  id: string
  character_id: string
  branch_id: string
  beliefs: Record<string, unknown>
  desires: Desire[]
  intentions: Intention[]
  memory: unknown[]
  private_knowledge: Record<string, unknown>
  last_updated_scene: number
  version: number
}

export interface ActionResult {
  action_id: string
  agent_id: string
  success: 'success' | 'partial' | 'failure'
  reason: string
  actual_outcome: string
}

export interface DMArbitration {
  round_id: string
  action_results: ActionResult[]
  conflicts_resolved: Array<{ agents: string[]; resolution: string }>
  environment_changes: Array<{ type: string; description: string }>
}

export interface ConvergenceCheck {
  next_anchor_id: string
  distance: number
  convergence_needed: boolean
  suggested_action?: string
}

export interface SimulationRoundResult {
  round_id: string
  agent_actions: AgentAction[]
  dm_arbitration: DMArbitration
  narrative_events: Array<Record<string, unknown>>
  sensory_seeds: Array<{ type: string; detail: string; char_id?: string }>
  convergence_score: number
  drama_score: number
  info_gain: number
  stagnation_count: number
}

export interface ReplanResult {
  success: boolean
  new_chapters: Array<Record<string, unknown>>
  modified_anchor?: Record<string, unknown>
  reason: string
}

export interface ReplanRequest {
  current_scene_id: string
  target_anchor_id: string
  world_state_snapshot: Record<string, unknown>
  failed_conditions: string[]
}

export interface FeedbackReport {
  trigger: string
  feedback: Record<string, unknown>
  corrections: Array<{ action: string }>
  severity: number
}

export type SimulationConfig = SimulationRoundResult

export interface SimulationState {
  id: string
  created_at: string
  status: string
}

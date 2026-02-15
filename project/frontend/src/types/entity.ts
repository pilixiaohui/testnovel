export interface EntityView {
  entity_id: string
  name?: string
  entity_type?: 'Character' | 'Location' | 'Item'
  tags: string[]
  arc_status?: string
  semantic_states: Record<string, unknown>
  has_agent?: boolean
  agent_state_id?: string
}

export interface EntityRelationView {
  from_entity_id: string
  to_entity_id: string
  relation_type: string
  tension: number
}

export interface StoryAnchor {
  id: string
  root_id: string
  branch_id: string
  sequence: number
  anchor_type: 'inciting_incident' | 'midpoint' | 'climax' | 'resolution' | string
  description: string
  constraint_type: 'hard' | 'soft' | 'flexible'
  required_conditions: string[]
  deadline_scene?: number
  achieved: boolean
}

export interface Subplot {
  id: string
  root_id: string
  branch_id: string
  title: string
  subplot_type: 'romance' | 'mystery' | 'rivalry' | string
  protagonist_id: string
  central_conflict: string
  status: 'dormant' | 'active' | 'resolved'
}

export interface SceneView {
  id: string
  branch_id: string
  status?: string
  pov_character_id?: string
  expected_outcome?: string
  conflict_type?: string
  actual_outcome: string
  summary?: string
  rendered_content?: string
  logic_exception?: boolean
  logic_exception_reason?: string
  is_dirty: boolean
  simulation_log_id?: string
  is_simulated?: boolean
}

export interface SceneContextView {
  root_id: string
  branch_id: string
  expected_outcome: string
  semantic_states: Record<string, unknown>
  summary: string
  scene_entities: EntityView[]
  characters: Array<{ entity_id: string; name?: string }>
  relations: EntityRelationView[]
  prev_scene_id?: string
  next_scene_id?: string
}

export interface WorldSnapshot {
  id: string
  scene_version_id: string
  branch_id: string
  scene_seq: number
  entity_states: Record<string, unknown>
  relations: EntityRelationView[]
}

export interface EntityBase {
  id: string
  created_at: string
  name: string
}

export interface EntityPosition {
  x: number
  y: number
  z: number
}

export interface WorldEntity extends EntityBase {
  type: string
  position: EntityPosition
}

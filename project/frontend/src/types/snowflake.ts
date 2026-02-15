export interface SnowflakeRoot {
  id?: string
  logline: string
  theme: string
  ending: string
  three_disasters: string[]
  created_at?: string
}

export interface CharacterSheet {
  id?: string
  entity_id?: string
  name: string
  ambition: string
  conflict: string
  epiphany: string
  voice_dna: string
  one_sentence_summary?: string
}

export interface SceneNode {
  id: string
  title: string
  sequence_index: number
  parent_act_id: string
  chapter_id?: string
  is_skeleton?: boolean
  branch_id?: string
  pov_character_id?: string
  expected_outcome?: string
  conflict_type?: string
  actual_outcome?: string
  is_dirty?: boolean
}

export interface Act {
  id: string
  root_id: string
  sequence: number
  title: string
  purpose: string
  tone: 'calm' | 'tense' | 'climax' | 'resolution'
}

export type ChapterReviewStatus = 'pending' | 'approved' | 'rejected'
export type ChapterReviewAction = Exclude<ChapterReviewStatus, 'pending'>

export interface Chapter {
  id: string
  act_id: string
  sequence: number
  title: string
  focus: string
  pov_character_id?: string
  word_count?: number
  review_status?: ChapterReviewStatus
}

export interface Step4Result {
  root_id: string
  branch_id: string
  scenes: SceneNode[]
}

export type SnowflakeStructure = SnowflakeRoot
export type SnowflakeCharacter = CharacterSheet
export type SnowflakeSceneNode = SceneNode
export type SnowflakeAct = Act
export type SnowflakeChapter = Chapter
export type SnowflakeStep4Result = Step4Result

export interface SnowflakeStep4Payload {
  root: SnowflakeRoot
  characters: CharacterSheet[]
}

export interface SnowflakeStep5Payload {
  root_id: string
  root: SnowflakeRoot
  characters: CharacterSheet[]
}

export type SnowflakeAnchor = Record<string, unknown>

export interface SnowflakeSteps {
  logline: string[]
  root: SnowflakeRoot | null
  characters: CharacterSheet[]
  scenes: SceneNode[]
  acts: Act[]
  chapters: Chapter[]
  anchors: SnowflakeAnchor[]
}

export type SnowflakeRootState = {
  id: string
  created_at: string
  steps: SnowflakeSteps
}

export type SnowflakePromptSet = {
  step1: string
  step2: string
  step3: string
  step4: string
  step5: string
  step6: string
}

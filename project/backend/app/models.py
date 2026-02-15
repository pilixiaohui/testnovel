"""核心领域模型定义，遵循雪花引擎 Phase 1 需求。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import TOPONE_MIN_TIMEOUT_SECONDS


class SnowflakeRoot(BaseModel):
    """雪花根节点：核心故事骨架。"""

    logline: str = Field(..., min_length=1, description="一句话核心故事")
    three_disasters: List[str] = Field(
        ..., min_length=3, max_length=3, description="三灾三难，长度必须为 3"
    )
    ending: str
    theme: str


class SnowflakePromptSet(BaseModel):
    step1: str
    step2: str
    step3: str
    step4: str
    step5: str
    step6: str


class LlmConfigView(BaseModel):
    model: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    temperature: float = Field(..., ge=0)
    max_tokens: int = Field(..., ge=1)
    timeout: int = Field(..., ge=1)
    system_instruction: str = Field(default="", max_length=4000)


class SystemConfigView(BaseModel):
    auto_save: bool
    ui_density: Literal["comfortable", "compact", "spacious"]


class AppSettingsView(BaseModel):
    llm_config: LlmConfigView
    system_config: SystemConfigView


class CharacterSheet(BaseModel):
    """人物小传。"""

    entity_id: UUID = Field(default_factory=uuid4)
    name: str
    ambition: str
    conflict: str
    epiphany: str
    voice_dna: str = Field(..., min_length=1, description="人物独特语气")

    @field_validator("voice_dna")
    @classmethod
    def ensure_voice_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("voice_dna must not be empty")
        return value


class SceneNode(BaseModel):
    """场景节点，面向 React Flow 渲染。"""

    id: UUID = Field(default_factory=uuid4)
    branch_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    sequence_index: int = Field(..., ge=0)
    parent_act_id: Optional[UUID] = None
    pov_character_id: Optional[UUID] = None
    expected_outcome: str
    conflict_type: str
    actual_outcome: str
    logic_exception: bool = False
    is_dirty: bool


class CharacterValidationResult(BaseModel):
    """角色校验结果，用于流程中的冲突检查。"""

    valid: bool
    issues: List[str] = Field(default_factory=list)


class Root(BaseModel):
    id: str
    logline: str
    theme: str
    ending: str
    created_at: Optional[str] = None


class Branch(BaseModel):
    id: str
    root_id: str
    branch_id: str
    parent_branch_id: Optional[str] = None
    fork_scene_origin_id: Optional[str] = None
    fork_commit_id: Optional[str] = None


class Commit(BaseModel):
    """不可变提交节点。"""

    id: str
    parent_id: Optional[str] = None
    root_id: str
    branch_id: Optional[str] = None
    created_at: str
    message: Optional[str] = None


class SceneOrigin(BaseModel):
    """场景身份节点（跨分支不变）。"""

    id: str
    root_id: str
    title: str
    initial_commit_id: str
    sequence_index: int
    parent_act_id: Optional[str] = None
    chapter_id: Optional[str] = None
    is_skeleton: bool = False


class SceneVersion(BaseModel):
    """场景版本节点（隶属于 Commit）。"""

    id: str
    scene_origin_id: str
    commit_id: str
    pov_character_id: str
    status: str
    expected_outcome: str
    conflict_type: str
    actual_outcome: str
    summary: Optional[str] = None
    rendered_content: Optional[str] = None
    logic_exception: bool = False
    logic_exception_reason: Optional[str] = None
    dirty: bool = False
    simulation_log_id: Optional[str] = None
    is_simulated: bool = False


class BranchHead(BaseModel):
    """分支 HEAD 指针节点。"""

    id: str
    root_id: str
    branch_id: str
    head_commit_id: str
    version: int


class Act(BaseModel):
    id: str
    root_id: str
    sequence: int
    title: str
    purpose: str
    tone: str


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Chapter(BaseModel):
    id: str
    act_id: str
    sequence: int
    title: str
    focus: str
    pov_character_id: Optional[str] = None
    rendered_content: Optional[str] = None
    review_status: ReviewStatus = ReviewStatus.pending


class ChapterReviewPayload(BaseModel):
    status: str


class StoryAnchor(BaseModel):
    id: str
    root_id: str
    branch_id: str
    sequence: int
    anchor_type: str
    description: str
    constraint_type: str
    required_conditions: str
    deadline_scene: Optional[int] = None
    achieved: bool = False


class CharacterAgentState(BaseModel):
    id: str
    character_id: str
    branch_id: str
    beliefs: str
    desires: str
    intentions: str
    memory: str
    private_knowledge: str
    last_updated_scene: int
    version: int = 1


class SimulationLog(BaseModel):
    id: str
    scene_version_id: str
    round_number: int
    agent_actions: str
    dm_arbitration: str
    narrative_events: str
    sensory_seeds: str
    convergence_score: float
    drama_score: float
    info_gain: float
    stagnation_count: int = 0


class Subplot(BaseModel):
    id: str
    root_id: str
    branch_id: str
    title: str
    subplot_type: str
    protagonist_id: str
    central_conflict: str
    status: str = "dormant"


class Entity(BaseModel):
    id: str
    root_id: str
    branch_id: str
    entity_type: str
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    semantic_states: Dict[str, object]
    arc_status: str
    has_agent: bool = False
    agent_state_id: Optional[str] = None


class WorldSnapshot(BaseModel):
    id: str
    scene_version_id: str
    branch_id: str
    scene_seq: int
    entity_states: Dict[str, object]
    relations: Optional[List[Dict[str, object]]] = None


class TemporalRelation(BaseModel):
    relation_type: str
    tension: int
    start_scene_seq: int
    end_scene_seq: Optional[int] = None
    branch_id: str
    created_at: Optional[str] = None
    invalidated_at: Optional[str] = None


DesireType = Literal["short_term", "long_term", "reactive"]
IntentionActionType = Literal[
    "attack", "flee", "negotiate", "investigate", "wait", "other"
]
ActionResultStatus = Literal["success", "partial", "failure"]


class Desire(BaseModel):
    """BDI: 角色欲望。"""

    id: str
    type: DesireType
    description: str
    priority: int = Field(..., ge=1, le=10)
    satisfaction_condition: str
    created_at_scene: int
    expires_at_scene: Optional[int] = None


class Intention(BaseModel):
    """BDI: 欲望转为行动意图。"""

    id: str
    desire_id: str
    action_type: IntentionActionType
    target: str
    expected_outcome: str
    risk_assessment: float = Field(..., ge=0, le=1)


class AgentAction(BaseModel):
    """BDI: 角色行动。"""

    agent_id: str
    internal_thought: str
    action_type: str
    action_target: str
    dialogue: Optional[str] = None
    action_description: str


class ActionResult(BaseModel):
    """DM: 行动结果。"""

    action_id: str
    agent_id: str
    success: ActionResultStatus
    reason: str
    actual_outcome: str


class DMArbitration(BaseModel):
    """DM: 裁决结果。"""

    round_id: str
    action_results: List[ActionResult]
    conflicts_resolved: List[Dict[str, object]] = Field(default_factory=list)
    environment_changes: List[Dict[str, object]] = Field(default_factory=list)


class ConvergenceCheck(BaseModel):
    """DM: 收敛性检查。"""

    next_anchor_id: str
    distance: float = Field(..., ge=0, le=1)
    convergence_needed: bool
    suggested_action: Optional[str] = None


class SimulationRoundResult(BaseModel):
    """推演: 单回合结果。"""

    round_id: str
    agent_actions: List[AgentAction]
    dm_arbitration: DMArbitration
    narrative_events: List[Dict[str, object]]
    sensory_seeds: List[Dict[str, object]]
    convergence_score: float
    drama_score: float
    info_gain: float
    stagnation_count: int


class FeedbackCorrection(BaseModel):
    """推演: 反馈修正动作。"""

    action: str

    def __getitem__(self, key: str) -> object:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)


class FeedbackReport(BaseModel):
    """推演: 递归反馈报告。"""

    trigger: str
    feedback: Dict[str, object]
    corrections: List[FeedbackCorrection]
    severity: float = Field(..., ge=0, le=1)


class ReplanRequest(BaseModel):
    """推演: 重新规划请求。"""

    current_scene_id: str
    target_anchor_id: str
    world_state_snapshot: Dict[str, object]
    failed_conditions: List[str]


class ReplanResult(BaseModel):
    """推演: 重新规划结果。"""

    success: bool
    new_chapters: List[Dict[str, object]]
    modified_anchor: Optional[Dict[str, object]] = None
    reason: str


class ToponeMessage(BaseModel):
    role: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class ToponeGeneratePayload(BaseModel):
    model: str | None = None
    system_instruction: str | None = None
    messages: List[ToponeMessage]
    generation_config: dict | None = None
    timeout: float | None = Field(default=None, ge=TOPONE_MIN_TIMEOUT_SECONDS)


class ImpactLevel(str, Enum):
    NEGLIGIBLE = "negligible"
    LOCAL = "local"
    CASCADING = "cascading"


class LogicCheckPayload(BaseModel):
    outline_requirement: str = Field(..., min_length=1)
    world_state: dict[str, Any] = Field(default_factory=dict)
    user_intent: str = Field(..., min_length=1)
    mode: str = Field(..., min_length=1)
    root_id: str | None = Field(default=None, min_length=1)
    branch_id: str | None = Field(default=None, min_length=1)
    scene_id: str | None = Field(default=None, min_length=1)
    force_reason: str | None = Field(default=None, min_length=1)


class LogicCheckResult(BaseModel):
    ok: bool
    mode: str
    decision: str
    impact_level: ImpactLevel
    warnings: List[str] = Field(default_factory=list)


class StateExtractPayload(BaseModel):
    content: str = Field(..., min_length=1)
    entity_ids: List[str] = Field(..., min_length=1)
    root_id: str | None = Field(default=None, min_length=1)
    branch_id: str | None = Field(default=None, min_length=1)


class SceneRenderPayload(BaseModel):
    voice_dna: str = Field(..., min_length=1)
    conflict_type: str = Field(..., min_length=1)
    outline_requirement: str = Field(..., min_length=1)
    user_intent: str = Field(..., min_length=1)
    expected_outcome: str = Field(..., min_length=1)
    world_state: dict[str, Any] = Field(default_factory=dict)
    logic_exception: bool | None = None
    force_reason: str | None = Field(default=None, min_length=1)


class StateProposal(BaseModel):
    entity_id: str = Field(..., min_length=1)
    entity_name: str | None = Field(default=None, min_length=1)
    confidence: float
    semantic_states_patch: dict[str, Any]
    semantic_states_before: dict[str, Any] | None = None
    semantic_states_after: dict[str, Any] | None = None
    evidence: str | None = None


class IdeaPayload(BaseModel):
    idea: str = Field(..., min_length=1, max_length=2000)

    @field_validator("idea")
    @classmethod
    def ensure_idea_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("idea must not be empty")
        return trimmed


class LoglinePayload(BaseModel):
    logline: str


class ScenePayload(BaseModel):
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


class Step4Result(BaseModel):
    root_id: str
    branch_id: str
    scenes: List[SceneNode]


class BranchPayload(BaseModel):
    branch_id: str = Field(..., min_length=1)


class BranchView(BaseModel):
    root_id: str
    branch_id: str


class SubplotCreatePayload(BaseModel):
    branch_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    subplot_type: str = Field(..., min_length=1)
    protagonist_id: str = Field(..., min_length=1)
    central_conflict: str = Field(..., min_length=1)


class CreateEntityPayload(BaseModel):
    name: str
    entity_type: str
    tags: list[str] = Field(default_factory=list)
    arc_status: str | None = None
    semantic_states: dict[str, Any] = Field(default_factory=dict)


class UpdateEntityPayload(BaseModel):
    name: str
    entity_type: str
    tags: list[str] = Field(default_factory=list)
    arc_status: str
    semantic_states: dict[str, Any] = Field(default_factory=dict)



class UpsertRelationPayload(BaseModel):
    from_entity_id: str = Field(..., min_length=1)
    to_entity_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    tension: int = Field(..., ge=0, le=100)


class EntityView(BaseModel):
    entity_id: str
    name: str | None = None
    entity_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    arc_status: str | None = None
    semantic_states: dict[str, Any] = Field(default_factory=dict)


class CharacterView(BaseModel):
    entity_id: str
    name: str | None = None
    ambition: str | None = None
    conflict: str | None = None
    epiphany: str | None = None
    voice_dna: str | None = None


class EntityRelationView(BaseModel):
    from_entity_id: str
    to_entity_id: str
    relation_type: str
    tension: int


class SceneView(BaseModel):
    id: str
    branch_id: str
    status: str | None = None
    pov_character_id: str | None = None
    expected_outcome: str | None = None
    conflict_type: str | None = None
    actual_outcome: str
    logic_exception: bool | None = None
    logic_exception_reason: str | None = None
    is_dirty: bool


class RootListItem(BaseModel):
    root_id: str
    name: str
    created_at: str | None = None
    updated_at: str | None = None


class ProjectCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, strict=True)

    @field_validator("name")
    @classmethod
    def ensure_name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name must not be empty")
        lowered = trimmed.lower()
        if "<script" in lowered or "drop table" in lowered:
            raise ValueError("name contains invalid characters")
        if not trimmed.isprintable():
            raise ValueError("name contains invalid characters")
        return trimmed


class RootListView(BaseModel):
    roots: List[RootListItem] = Field(default_factory=list)


class RootGraphView(BaseModel):
    root_id: str
    branch_id: str
    logline: str | None = None
    theme: str | None = None
    ending: str | None = None
    characters: List[CharacterView] = Field(default_factory=list)
    scenes: List[SceneView] = Field(default_factory=list)
    relations: List[EntityRelationView] = Field(default_factory=list)


class StructureTreeActView(BaseModel):
    act_id: str
    act_index: int | None = None
    disaster: str | None = None
    scene_ids: List[str] = Field(default_factory=list)


class StructureTreeView(BaseModel):
    root_id: str
    branch_id: str
    acts: List[StructureTreeActView] = Field(default_factory=list)


class SceneReorderPayload(BaseModel):
    branch_id: str = Field(..., min_length=1)
    scene_ids: List[str] = Field(..., min_length=1)


class SceneReorderResult(BaseModel):
    ok: bool
    root_id: str
    branch_id: str
    scene_ids: List[str] = Field(default_factory=list)


class SceneContextView(BaseModel):
    root_id: str
    branch_id: str
    expected_outcome: str
    semantic_states: dict[str, Any]
    summary: str
    scene_entities: List[EntityView] = Field(default_factory=list)
    characters: List[CharacterView] = Field(default_factory=list)
    relations: List[EntityRelationView] = Field(default_factory=list)
    prev_scene_id: str | None = None
    next_scene_id: str | None = None


class SceneCompletePayload(BaseModel):
    actual_outcome: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


class SceneCompletionOrchestratePayload(BaseModel):
    root_id: str = Field(..., min_length=1)
    branch_id: str = Field(..., min_length=1)
    outline_requirement: str = Field(..., min_length=1)
    world_state: dict[str, Any] = Field(default_factory=dict)
    user_intent: str = Field(..., min_length=1)
    mode: str = Field(..., min_length=1)
    force_reason: str | None = Field(default=None, min_length=1)
    content: str = Field(..., min_length=1)
    entity_ids: List[str] = Field(..., min_length=1)
    confirmed_proposals: List[StateProposal] = Field(...)
    actual_outcome: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


class SceneCompletionResult(BaseModel):
    ok: bool
    scene_id: str
    root_id: str
    branch_id: str
    status: str
    actual_outcome: str
    summary: str
    logic_check: LogicCheckResult
    extracted_proposals: List[StateProposal]
    confirmed_count: int
    applied: int
    updated_entities: List[dict[str, Any]]


class SceneRenderResult(BaseModel):
    ok: bool
    scene_id: str
    branch_id: str
    content: str


class ForkFromCommitPayload(BaseModel):
    source_commit_id: str = Field(..., min_length=1)
    new_branch_id: str = Field(..., min_length=1)
    parent_branch_id: str | None = None


class ForkFromScenePayload(BaseModel):
    source_branch_id: str = Field(..., min_length=1)
    scene_origin_id: str = Field(..., min_length=1)
    new_branch_id: str = Field(..., min_length=1)
    commit_id: str | None = None


class ResetBranchPayload(BaseModel):
    commit_id: str = Field(..., min_length=1)


class CommitScenePayload(BaseModel):
    scene_origin_id: str = Field(..., min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(..., min_length=1)
    expected_head_version: int | None = None


class CommitResult(BaseModel):
    commit_id: str
    scene_version_ids: List[str] = Field(default_factory=list)


class CreateSceneOriginPayload(BaseModel):
    title: str = Field(..., min_length=1)
    parent_act_id: str = Field(..., min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)


class CreateSceneOriginResult(BaseModel):
    commit_id: str
    scene_origin_id: str
    scene_version_id: str


class DeleteSceneOriginPayload(BaseModel):
    message: str = Field(..., min_length=1)


class GcPayload(BaseModel):
    retention_days: int = Field(..., ge=0)


class GcResult(BaseModel):
    deleted_commit_ids: List[str] = Field(default_factory=list)
    deleted_scene_version_ids: List[str] = Field(default_factory=list)


class Step5aPayload(BaseModel):
    root_id: str = Field(..., min_length=1)
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


class Step5bPayload(BaseModel):
    root_id: str = Field(..., min_length=1)
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


class SaveSnowflakeStepPayload(BaseModel):
    step: Literal["step1", "step2", "step3", "step4", "step5", "step6"]
    data: dict[str, Any] = Field(default_factory=dict)

class AnchorCreatePayload(BaseModel):
    branch_id: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=1)
    anchor_type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    constraint_type: str = Field(..., min_length=1)
    required_conditions: List[str] = Field(default_factory=list)


class AnchorUpdatePayload(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    constraint_type: str | None = Field(default=None, min_length=1)
    required_conditions: List[str] | None = None
    achieved: bool | None = None


class AnchorCheckPayload(BaseModel):
    scene_version_id: str | None = None
    world_state: dict[str, Any] = Field(default_factory=dict)


class AgentInitPayload(BaseModel):
    branch_id: str = Field(..., min_length=1)
    initial_desires: List[dict[str, Any]] = Field(default_factory=list)


class AnchorGeneratePayload(BaseModel):
    branch_id: str = Field(..., min_length=1)
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


class AgentDesiresPayload(BaseModel):
    desires: List[Desire] = Field(default_factory=list)


class AgentDecidePayload(BaseModel):
    scene_context: dict[str, Any]


class DMArbitratePayload(BaseModel):
    round_id: str = Field(..., min_length=1)
    actions: List[dict[str, Any]]
    world_state: dict[str, Any]


class DMConvergePayload(BaseModel):
    world_state: dict[str, Any]
    next_anchor: dict[str, Any]


class DMIntervenePayload(BaseModel):
    check: dict[str, Any]
    world_state: dict[str, Any]


class DMReplanPayload(BaseModel):
    current_scene: str = Field(..., min_length=1)
    target_anchor: dict[str, Any]
    world_state: dict[str, Any]


class SimulationRoundPayload(BaseModel):
    scene_context: dict[str, Any]
    agents: List[dict[str, Any]]
    round_id: str = Field(..., min_length=1)


class SimulationScenePayload(BaseModel):
    scene_context: dict[str, Any]
    max_rounds: int = Field(..., ge=1)


class RenderScenePayload(BaseModel):
    rounds: List[dict[str, Any]]
    scene: dict[str, Any]


class FeedbackLoopPayload(BaseModel):
    scene_context: dict[str, Any]
    rounds: List[SimulationRoundResult]

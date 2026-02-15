"""GQLAlchemy schema models for Memgraph."""

from __future__ import annotations

from gqlalchemy import Node, Relationship

INDEX_DEFINITIONS = [
    {"label": "Root", "property": "id"},
    {"label": "Branch", "property": "id"},
    {"label": "Branch", "properties": ["root_id", "branch_id"]},
    {"label": "BranchHead", "property": "id"},
    {"label": "BranchHead", "properties": ["root_id", "branch_id"]},
    {"label": "Commit", "property": "id"},
    {"label": "Commit", "property": "root_id"},
    {"label": "SceneOrigin", "property": "id"},
    {"label": "SceneOrigin", "properties": ["root_id", "sequence_index"]},
    {"label": "SceneOrigin", "property": "chapter_id"},
    {"label": "SceneOrigin", "property": "is_skeleton"},
    {"label": "SceneVersion", "property": "id"},
    {"label": "SceneVersion", "property": "scene_origin_id"},
    {"label": "SceneVersion", "property": "commit_id"},
    {"label": "SceneVersion", "property": "simulation_log_id"},
    {"label": "SceneVersion", "property": "is_simulated"},
    {"label": "Entity", "property": "id"},
    {"label": "Entity", "property": "branch_id"},
    {"label": "Entity", "properties": ["root_id", "branch_id"]},
    {"label": "Entity", "property": "has_agent"},
    {"label": "Entity", "property": "agent_state_id"},
    {"label": "Act", "property": "id"},
    {"label": "Act", "property": "root_id"},
    {"label": "Chapter", "property": "id"},
    {"label": "Chapter", "property": "act_id"},
    {"label": "StoryAnchor", "property": "id"},
    {"label": "StoryAnchor", "properties": ["root_id", "branch_id"]},
    {"label": "Subplot", "property": "id"},
    {"label": "Subplot", "properties": ["root_id", "branch_id"]},
    {"label": "CharacterAgentState", "property": "id"},
    {"label": "CharacterAgentState", "property": "character_id"},
    {"label": "CharacterAgentState", "property": "branch_id"},
    {"label": "SimulationLog", "property": "id"},
    {"label": "SimulationLog", "property": "scene_version_id"},
    {"label": "WorldSnapshot", "property": "id"},
    {"label": "WorldSnapshot", "property": "scene_version_id"},
    {"label": "WorldSnapshot", "properties": ["branch_id", "scene_seq"]},
    {"label": "TemporalRelation", "properties": ["branch_id", "start_scene_seq"]},
    {"label": "TemporalRelation", "properties": ["branch_id", "end_scene_seq"]},
]


class Root(Node):
    __label__ = "Root"
    id: str
    logline: str
    theme: str
    ending: str
    created_at: str | None = None


class Branch(Node):
    __label__ = "Branch"
    id: str
    root_id: str
    branch_id: str
    parent_branch_id: str | None = None
    fork_scene_origin_id: str | None = None
    fork_commit_id: str | None = None


class BranchHead(Node):
    __label__ = "BranchHead"
    id: str
    root_id: str
    branch_id: str
    head_commit_id: str
    version: int


class Commit(Node):
    __label__ = "Commit"
    id: str
    parent_id: str | None = None
    message: str | None = None
    created_at: str
    root_id: str
    branch_id: str | None = None


class Act(Node):
    __label__ = "Act"
    id: str
    root_id: str
    sequence: int
    title: str
    purpose: str
    tone: str


class Chapter(Node):
    __label__ = "Chapter"
    id: str
    act_id: str
    sequence: int
    title: str
    focus: str
    pov_character_id: str | None
    rendered_content: str | None = None
    review_status: str = "pending"


class StoryAnchor(Node):
    __label__ = "StoryAnchor"
    id: str
    root_id: str
    branch_id: str
    sequence: int
    anchor_type: str
    description: str
    constraint_type: str
    required_conditions: str
    deadline_scene: int | None = None
    achieved: bool = False


class CharacterAgentState(Node):
    __label__ = "CharacterAgentState"
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


class SimulationLog(Node):
    __label__ = "SimulationLog"
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


class Subplot(Node):
    __label__ = "Subplot"
    id: str
    root_id: str
    branch_id: str
    title: str
    subplot_type: str
    protagonist_id: str
    central_conflict: str
    status: str = "dormant"


class SceneOrigin(Node):
    __label__ = "SceneOrigin"
    id: str
    root_id: str
    title: str
    initial_commit_id: str
    sequence_index: int
    parent_act_id: str | None = None
    chapter_id: str | None = None
    is_skeleton: bool = False


class SceneVersion(Node):
    __label__ = "SceneVersion"
    id: str
    scene_origin_id: str
    commit_id: str
    pov_character_id: str
    status: str
    expected_outcome: str
    conflict_type: str
    actual_outcome: str
    summary: str | None = None
    rendered_content: str | None = None
    logic_exception: bool = False
    logic_exception_reason: str | None = None
    dirty: bool = False
    simulation_log_id: str | None = None
    is_simulated: bool = False


class Entity(Node):
    __label__ = "Entity"
    id: str
    root_id: str
    branch_id: str
    entity_type: str
    name: str | None = None
    tags: list[str] | None = None
    semantic_states: dict[str, object]
    arc_status: str
    has_agent: bool = False
    agent_state_id: str | None = None


class WorldSnapshot(Node):
    __label__ = "WorldSnapshot"
    id: str
    scene_version_id: str
    branch_id: str
    scene_seq: int
    entity_states: dict[str, object]
    relations: list[dict[str, object]] | None = None


class TemporalRelation(Relationship):
    __type__ = "TemporalRelation"
    relation_type: str
    tension: int
    start_scene_seq: int
    end_scene_seq: int | None = None
    branch_id: str
    created_at: str | None = None
    invalidated_at: str | None = None


class HEAD(Relationship):
    __type__ = "HEAD"


class PARENT(Relationship):
    __type__ = "PARENT"


class INCLUDES(Relationship):
    __type__ = "INCLUDES"


class OF_ORIGIN(Relationship):
    __type__ = "OF_ORIGIN"



class EstablishesState(Relationship):
    __type__ = "ESTABLISHES_STATE"


class CONTAINS_CHAPTER(Relationship):
    __type__ = "CONTAINS_CHAPTER"


class CONTAINS_SCENE(Relationship):
    __type__ = "CONTAINS_SCENE"


class DEPENDS_ON(Relationship):
    __type__ = "DEPENDS_ON"


class TRIGGERED_AT(Relationship):
    __type__ = "TRIGGERED_AT"


class AGENT_OF(Relationship):
    __type__ = "AGENT_OF"

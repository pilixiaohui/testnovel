"""共享测试 stub — 所有测试文件应从此处导入，避免接口漂移。"""
from __future__ import annotations

from app.constants import DEFAULT_BRANCH_ID
from app.models import (
    ActionResult,
    AgentAction,
    DMArbitration,
    SimulationRoundResult,
)


# ---------------------------------------------------------------------------
# Helper builders (shared across simulation tests)
# ---------------------------------------------------------------------------

def build_agent_action() -> AgentAction:
    return AgentAction(
        agent_id="agent-1",
        internal_thought="wait",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="pause",
    )


def build_action_result() -> ActionResult:
    return ActionResult(
        action_id="act-1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="clear",
    )


def build_dm_arbitration() -> DMArbitration:
    return DMArbitration(round_id="round-1", action_results=[build_action_result()])


def build_round_result() -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[build_agent_action()],
        dm_arbitration=build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.2,
        drama_score=0.3,
        info_gain=0.4,
        stagnation_count=0,
    )


# ---------------------------------------------------------------------------
# SimulationEngineStub — mirrors app.services.simulation_engine.SimulationEngine
# ---------------------------------------------------------------------------

class SimulationEngineStub:
    """对应 app.services.simulation_engine.SimulationEngine"""

    class _CharacterEngine:
        async def decide(self, _agent_id, _scene_context):
            return {
                "agent_id": "agent-1",
                "internal_thought": "wait",
                "action_type": "wait",
                "action_target": "",
                "dialogue": None,
                "action_description": "pause",
            }

    def __init__(self) -> None:
        self.character_engine = self._CharacterEngine()

    async def run_round(self, scene_context, agents, config):
        return build_round_result()

    async def run_scene(self, scene_context, config):
        return "rendered content"


class SimulationEngineValueErrorStub(SimulationEngineStub):
    """run_scene raises ValueError — for testing 422 mapping."""

    async def run_scene(self, scene_context, config):
        raise ValueError("world_state is required for convergence flow")


# ---------------------------------------------------------------------------
# GraphStorageStub — mirrors app.storage.ports.GraphStoragePort
# ---------------------------------------------------------------------------

class GraphStorageStub:
    """对应 app.storage.ports.GraphStoragePort 的最小可用 stub。"""

    def __init__(self) -> None:
        self.states: dict[str, dict] = {}
        self.dirty: set[str] = set()
        self.required: list[tuple[str, str]] = []
        self.branches: set[str] = {DEFAULT_BRANCH_ID}
        self.entity_counter = 0
        self.entities: dict[str, dict] = {}
        self.rendered: dict[str, str] = {}
        self.completed: dict[str, dict] = {}
        self.logic_exceptions: dict[tuple[str, str, str], str] = {}
        self.logic_world_state_calls: list[tuple[str, str, str]] = []
        self.local_fixes: list[tuple[str, str, str, int]] = []
        self.future_dirty_calls: list[tuple[str, str, str]] = []
        self.created_project_name: str | None = None
        self.deleted_root_id: str | None = None

    def require_root(self, *, root_id: str, branch_id: str) -> None:
        self.required.append((root_id, branch_id))

    def get_entity_semantic_states(
        self, *, root_id: str, branch_id: str, entity_id: str
    ) -> dict:
        return self.states.get(entity_id, {}).copy()

    def build_logic_check_world_state(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> dict:
        self.logic_world_state_calls.append((root_id, branch_id, scene_id))
        return {"root_id": root_id, "branch_id": branch_id, "scene_id": scene_id}

    def mark_scene_logic_exception(
        self, *, root_id: str, branch_id: str, scene_id: str, reason: str
    ) -> None:
        self.logic_exceptions[(root_id, branch_id, scene_id)] = reason

    def is_scene_logic_exception(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> bool:
        return (root_id, branch_id, scene_id) in self.logic_exceptions

    def apply_local_scene_fix(
        self, *, root_id: str, branch_id: str, scene_id: str, limit: int = 3
    ) -> list[str]:
        self.local_fixes.append((root_id, branch_id, scene_id, limit))
        return [scene_id]

    def mark_future_scenes_dirty(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> list[str]:
        self.future_dirty_calls.append((root_id, branch_id, scene_id))
        return [scene_id]

    def apply_semantic_states_patch(
        self, *, root_id: str, branch_id: str, entity_id: str, patch: dict
    ) -> dict:
        current = self.states.get(entity_id, {})
        updated = {**current, **patch}
        self.states[entity_id] = updated
        return updated

    def mark_scene_dirty(self, *, scene_id: str, branch_id: str) -> None:
        self.dirty.add(scene_id)

    def list_dirty_scenes(self, *, root_id: str, branch_id: str) -> list[str]:
        return sorted(self.dirty)

    def create_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id in self.branches:
            raise ValueError("already exists")
        self.branches.add(branch_id)

    def list_branches(self, *, root_id: str) -> list[str]:
        return sorted(self.branches)

    def require_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def merge_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def revert_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def fork_from_commit(
        self,
        *,
        root_id: str,
        source_commit_id: str,
        new_branch_id: str,
        parent_branch_id: str | None = None,
        fork_scene_origin_id: str | None = None,
    ) -> None:
        self.branches.add(new_branch_id)

    def fork_from_scene(
        self,
        *,
        root_id: str,
        source_branch_id: str,
        scene_origin_id: str,
        new_branch_id: str,
        commit_id: str | None = None,
    ) -> None:
        self.branches.add(new_branch_id)

    def reset_branch_head(
        self, *, root_id: str, branch_id: str, commit_id: str
    ) -> None:
        return

    def get_branch_history(
        self, *, root_id: str, branch_id: str, limit: int = 50
    ) -> list[dict]:
        return [
            {
                "id": "commit-1",
                "parent_id": None,
                "root_id": root_id,
                "created_at": "2025-01-01T00:00:00Z",
                "message": "commit",
            }
        ]

    def get_root_snapshot(self, *, root_id: str, branch_id: str) -> dict:
        return {
            "root_id": root_id,
            "branch_id": branch_id,
            "logline": "logline",
            "theme": "theme",
            "ending": "ending",
            "characters": [],
            "scenes": [],
            "relations": [],
        }

    def create_entity(
        self,
        *,
        root_id: str,
        branch_id: str,
        name: str,
        entity_type: str,
        tags: list[str],
        arc_status: str | None,
        semantic_states: dict,
    ) -> str:
        self.entity_counter += 1
        entity_id = f"entity-{self.entity_counter}"
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "name": name,
            "entity_type": entity_type,
            "tags": tags,
            "arc_status": arc_status,
            "semantic_states": semantic_states,
        }
        return entity_id

    def list_entities(self, *, root_id: str, branch_id: str) -> list[dict]:
        return list(self.entities.values())

    def upsert_entity_relation(
        self,
        *,
        root_id: str,
        branch_id: str,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        tension: int,
    ) -> None:
        return

    def get_scene_context(self, *, scene_id: str, branch_id: str) -> dict:
        return {
            "root_id": "root",
            "branch_id": branch_id,
            "expected_outcome": "Outcome 1",
            "semantic_states": {},
            "summary": "Summary 1",
            "scene_entities": [],
            "characters": [],
            "relations": [],
            "prev_scene_id": None,
            "next_scene_id": None,
        }

    def diff_scene_versions(
        self, *, scene_origin_id: str, from_commit_id: str, to_commit_id: str
    ) -> dict:
        return {"actual_outcome": {"from": "", "to": "updated"}}

    def commit_scene(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_origin_id: str,
        content: dict,
        message: str,
        expected_head_version: int | None = None,
    ) -> dict:
        return {"commit_id": "commit-1", "scene_version_ids": ["version-1"]}

    def create_scene_origin(
        self,
        *,
        root_id: str,
        branch_id: str,
        title: str,
        parent_act_id: str,
        content: dict,
    ) -> dict:
        return {
            "commit_id": "commit-1",
            "scene_origin_id": "origin-1",
            "scene_version_id": "version-1",
        }

    def delete_scene_origin(
        self, *, root_id: str, branch_id: str, scene_origin_id: str, message: str
    ) -> dict:
        return {"commit_id": "commit-2", "scene_version_ids": []}

    def gc_orphan_commits(self, *, retention_days: int) -> dict:
        return {
            "deleted_commit_ids": ["commit-1"],
            "deleted_scene_version_ids": ["version-1"],
        }

    def save_snowflake(self, root, characters, scenes) -> str:
        self.created_project_name = root.logline
        return "root-created"

    def delete_root(self, root_id: str) -> None:
        self.deleted_root_id = root_id

    def save_scene_render(self, *, scene_id: str, branch_id: str, content: str) -> None:
        self.rendered[scene_id] = content

    def complete_scene(
        self, *, scene_id: str, branch_id: str, actual_outcome: str, summary: str
    ) -> None:
        self.completed[scene_id] = {
            "actual_outcome": actual_outcome,
            "summary": summary,
        }

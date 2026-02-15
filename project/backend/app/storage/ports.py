from __future__ import annotations

from typing import Any, Iterable, Protocol, Sequence

from app.models import CharacterSheet, Entity, SceneNode, SnowflakeRoot


class GraphStoragePort(Protocol):
    def save_snowflake(
        self,
        root: SnowflakeRoot,
        characters: Sequence[CharacterSheet],
        scenes: Sequence[SceneNode],
    ) -> str: ...

    def list_roots(self, *, limit: int, offset: int) -> list[dict[str, Any]]: ...

    def create_branch(self, *, root_id: str, branch_id: str) -> None: ...

    def list_branches(self, *, root_id: str) -> list[str]: ...

    def require_branch(self, *, root_id: str, branch_id: str) -> None: ...

    def merge_branch(self, *, root_id: str, branch_id: str) -> None: ...

    def revert_branch(self, *, root_id: str, branch_id: str) -> None: ...

    def fork_from_commit(
        self,
        *,
        root_id: str,
        source_commit_id: str,
        new_branch_id: str,
        parent_branch_id: str | None = None,
        fork_scene_origin_id: str | None = None,
    ) -> None: ...

    def fork_from_scene(
        self,
        *,
        root_id: str,
        source_branch_id: str,
        scene_origin_id: str,
        new_branch_id: str,
        commit_id: str | None = None,
    ) -> None: ...

    def reset_branch_head(self, *, root_id: str, branch_id: str, commit_id: str) -> None: ...

    def get_branch_history(
        self, *, root_id: str, branch_id: str, limit: int = 50
    ) -> list[dict[str, Any]]: ...

    def commit_scene(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_origin_id: str,
        content: dict[str, Any],
        message: str,
        expected_head_version: int | None = None,
    ) -> dict[str, Any]: ...

    def create_scene_origin(
        self,
        *,
        root_id: str,
        branch_id: str,
        title: str,
        parent_act_id: str,
        content: dict[str, Any],
    ) -> dict[str, Any]: ...

    def gc_orphan_commits(self, *, retention_days: int) -> dict[str, list[str]]: ...

    def get_root_snapshot(self, *, root_id: str, branch_id: str) -> dict[str, Any]: ...

    def create_entity(
        self,
        *,
        root_id: str,
        branch_id: str,
        name: str,
        entity_type: str,
        tags: Iterable[str],
        arc_status: str | None,
        semantic_states: dict[str, Any],
    ) -> str: ...

    def list_entities(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]: ...

    def update_entity(self, entity: Entity) -> Entity: ...

    def delete_entity(self, *, entity_id: str) -> None: ...

    def upsert_entity_relation(
        self,
        *,
        root_id: str,
        branch_id: str,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        tension: int,
    ) -> None: ...

    def get_scene_context(self, *, scene_id: str, branch_id: str) -> dict[str, Any]: ...

    def diff_scene_versions(
        self, *, scene_origin_id: str, from_commit_id: str, to_commit_id: str
    ) -> dict[str, dict[str, Any]]: ...

    def delete_scene_origin(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_origin_id: str,
        message: str,
    ) -> dict[str, Any]: ...

    def save_scene_render(self, *, scene_id: str, branch_id: str, content: str) -> None: ...

    def complete_scene(
        self,
        *,
        scene_id: str,
        branch_id: str,
        actual_outcome: str,
        summary: str,
    ) -> None: ...

    def mark_scene_logic_exception(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
        reason: str,
    ) -> None: ...

    def is_scene_logic_exception(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> bool: ...

    def mark_scene_dirty(self, *, scene_id: str, branch_id: str) -> None: ...

    def list_dirty_scenes(self, *, root_id: str, branch_id: str) -> list[str]: ...

    def require_root(self, *, root_id: str, branch_id: str) -> None: ...

    def get_entity_semantic_states(
        self, *, root_id: str, branch_id: str, entity_id: str
    ) -> dict[str, Any]: ...

    def apply_semantic_states_patch(
        self,
        *,
        root_id: str,
        branch_id: str,
        entity_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]: ...

    def apply_local_scene_fix(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
        limit: int = 3,
    ) -> list[str]: ...

    def mark_future_scenes_dirty(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
    ) -> list[str]: ...

    def build_logic_check_world_state(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> dict[str, Any]: ...

    def create_act(
        self, *, root_id: str, seq: int, title: str, purpose: str, tone: str
    ) -> dict[str, Any]: ...

    def get_act(self, act_id: str) -> Any: ...

    def update_act(self, act: Any) -> Any: ...

    def delete_act(self, act_id: str) -> None: ...

    def list_acts(self, *, root_id: str) -> list[dict[str, Any]]: ...

    def create_chapter(
        self,
        *,
        act_id: str,
        seq: int,
        title: str,
        focus: str,
        pov_character_id: str | None = None,
        rendered_content: str | None = None,
        review_status: str = "pending",
    ) -> dict[str, Any]: ...

    def get_chapter(self, chapter_id: str) -> Any: ...

    def update_chapter(self, chapter: Any) -> Any: ...

    def delete_chapter(self, chapter_id: str) -> None: ...

    def list_chapters(self, *, act_id: str) -> list[dict[str, Any]]: ...

    def link_scene_to_chapter(self, *, scene_id: str, chapter_id: str) -> None: ...

    def create_anchor(
        self,
        *,
        root_id: str,
        branch_id: str,
        seq: int,
        type: str,
        desc: str,
        constraint: str,
        conditions: str,
    ) -> dict[str, Any]: ...

    def get_anchor(self, anchor_id: str) -> Any: ...

    def update_anchor(self, anchor: Any) -> Any: ...

    def delete_anchor(self, anchor_id: str) -> None: ...

    def mark_anchor_achieved(
        self, *, anchor_id: str, scene_version_id: str
    ) -> dict[str, Any]: ...

    def list_anchors(
        self, *, root_id: str, branch_id: str
    ) -> list[dict[str, Any]]: ...

    def get_next_unachieved_anchor(
        self, *, root_id: str, branch_id: str
    ) -> dict[str, Any]: ...

    def init_character_agent(
        self, *, char_id: str, branch_id: str, initial_desires: list[dict[str, Any]]
    ) -> dict[str, Any]: ...

    def get_agent_state(self, agent_id: str) -> Any: ...

    def delete_agent_state(self, agent_id: str) -> None: ...

    def update_agent_desires(
        self, *, agent_id: str, desires: list[dict[str, Any]]
    ) -> dict[str, Any]: ...

    def update_agent_beliefs(
        self, *, agent_id: str, beliefs_patch: dict[str, Any]
    ) -> dict[str, Any]: ...

    def add_agent_memory(self, *, agent_id: str, entry: dict[str, Any]) -> dict[str, Any]: ...

    def create_simulation_log(self, log: Any) -> Any: ...

    def get_simulation_log(self, log_id: str) -> Any: ...

    def list_simulation_logs(self, scene_id: str) -> list[Any]: ...

    def update_simulation_log(self, log: Any) -> Any: ...

    def delete_simulation_log(self, log_id: str) -> None: ...

    def create_subplot(self, subplot: Any) -> Any: ...

    def get_subplot(self, subplot_id: str) -> Any: ...

    def update_subplot(self, subplot: Any) -> Any: ...

    def list_subplots(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]: ...

    def delete_subplot(self, subplot_id: str) -> None: ...

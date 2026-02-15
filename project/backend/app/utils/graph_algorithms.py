"""Graph algorithms for dependency and impact analysis."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_entity_scene_index(
    scene_entities: Mapping[str, Sequence[str]],
) -> dict[str, set[str]]:
    entity_to_scenes: dict[str, set[str]] = {}
    for scene_id, entities in scene_entities.items():
        for entity_id in entities:
            entity_to_scenes.setdefault(entity_id, set()).add(scene_id)
    return entity_to_scenes


def collect_impacted_scenes(
    entity_to_scenes: Mapping[str, set[str]],
    entity_ids: Sequence[str],
) -> list[str]:
    impacted: set[str] = set()
    for entity_id in entity_ids:
        impacted.update(entity_to_scenes[entity_id])
    return list(impacted)


def calculate_impact_severity(state_changes: Sequence[Mapping[str, Any]]) -> str:
    change_count = len(state_changes)
    if change_count >= 3:
        return "high"
    if change_count == 2:
        return "medium"
    return "low"


def build_impact_reason(
    scene_id: str,
    state_changes: Sequence[Mapping[str, Any]],
) -> str:
    entities = [change["entity_id"] for change in state_changes]
    joined = ", ".join(entities)
    return (
        f"{len(state_changes)} state change(s) on {joined} "
        f"may affect scene {scene_id}"
    )

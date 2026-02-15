"""Dependency matrix for scene entity relationships."""

from __future__ import annotations

import asyncio
import inspect
from typing import Awaitable, Callable, Mapping, Sequence

from app.utils.graph_algorithms import (
    build_entity_scene_index,
    collect_impacted_scenes,
)


class DependencyMatrix:
    def __init__(
        self,
        entity_to_scenes: dict[str, set[str]],
        scene_sequences: Mapping[str, int] | None = None,
    ) -> None:
        self._entity_to_scenes = entity_to_scenes
        self._scene_sequences = scene_sequences

    @classmethod
    def from_scene_entities(
        cls,
        scene_entities: Mapping[str, Sequence[str]],
        *,
        scene_sequences: Mapping[str, int] | None = None,
    ) -> "DependencyMatrix":
        return cls(
            build_entity_scene_index(scene_entities),
            scene_sequences=scene_sequences,
        )

    def get_impacted_scenes(self, entity_ids: Sequence[str]) -> list[str]:
        return collect_impacted_scenes(self._entity_to_scenes, entity_ids)

    def filter_scenes_after(
        self,
        scene_ids: Sequence[str],
        *,
        min_scene_seq: int,
    ) -> list[str]:
        return [
            scene_id
            for scene_id in scene_ids
            if self._scene_sequences[scene_id] > min_scene_seq
        ]


class DependencyMatrixCache:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], object] = {}

    def get_or_build(
        self,
        *,
        root_id: str,
        branch_id: str,
        builder: Callable[[], DependencyMatrix | Awaitable[DependencyMatrix]],
    ) -> DependencyMatrix | Awaitable[DependencyMatrix]:
        key = (root_id, branch_id)
        if key in self._cache:
            return self._cache[key]
        result = builder()
        if inspect.isawaitable(result):
            task = asyncio.create_task(result)
            self._cache[key] = task
            return task
        self._cache[key] = result
        return result

    def invalidate(self, *, root_id: str, branch_id: str) -> None:
        del self._cache[(root_id, branch_id)]

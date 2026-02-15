"""Scene impact analyzer based on state changes."""

from __future__ import annotations

import inspect
from typing import Any, Mapping, Sequence

from app.services.dependency_matrix import DependencyMatrix, DependencyMatrixCache
from app.utils.graph_algorithms import build_impact_reason, calculate_impact_severity


class ImpactAnalyzer:
    def __init__(
        self,
        db: Any,
        dependency_matrix_cache: DependencyMatrixCache | None = None,
    ) -> None:
        self._db = db
        self._dependency_matrix_cache = dependency_matrix_cache

    async def _get_root_id(self, branch_id: str) -> str:
        rows = await self._db.execute_and_fetch(
            "MATCH (r:Root {branch_id: $branch_id}) "
            "RETURN r.id AS root_id LIMIT 1",
            {"branch_id": branch_id},
        )
        return rows[0]["root_id"]

    async def _get_scene_sequence(self, scene_id: str) -> int:
        rows = await self._db.execute_and_fetch(
            "MATCH (s:Scene {id: $scene_id}) "
            "RETURN s.scene_seq AS scene_seq LIMIT 1",
            {"scene_id": scene_id},
        )
        return rows[0]["scene_seq"]

    @staticmethod
    def _calculate_severity(state_changes: Sequence[Mapping[str, Any]]) -> str:
        return calculate_impact_severity(state_changes)

    @staticmethod
    def _build_reason(
        scene_id: str,
        state_changes: Sequence[Mapping[str, Any]],
    ) -> str:
        return build_impact_reason(scene_id, state_changes)

    async def _build_dependency_matrix(self, root_id: str) -> DependencyMatrix:
        rows = await self._db.execute_and_fetch(
            "MATCH (r:Root {id: $root_id})-[:HAS_SCENE]->(s:Scene) "
            "RETURN s.id AS scene_id, s.involved_entities AS involved_entities, "
            "s.scene_seq AS scene_seq",
            {"root_id": root_id},
        )
        return DependencyMatrix.from_scene_entities(
            {row["scene_id"]: row["involved_entities"] for row in rows},
            scene_sequences={row["scene_id"]: row["scene_seq"] for row in rows},
        )

    async def analyze_scene_impact(
        self,
        *,
        scene_id: str,
        branch_id: str,
        state_changes: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        root_id = await self._get_root_id(branch_id)
        scene_seq = await self._get_scene_sequence(scene_id)
        entity_ids = [change["entity_id"] for change in state_changes]

        if self._dependency_matrix_cache is None:
            rows = await self._db.execute_and_fetch(
                "MATCH (r:Root {id: $root_id})-[:HAS_SCENE]->(s:Scene) "
                "WHERE s.scene_seq > $scene_seq "
                "AND any(entity_id IN $entity_ids WHERE entity_id IN s.involved_entities) "
                "RETURN s.id AS scene_id, s.scene_seq AS scene_seq, "
                "s.involved_entities AS involved_entities",
                {
                    "root_id": root_id,
                    "scene_seq": scene_seq,
                    "entity_ids": entity_ids,
                },
            )
            impacted_scene_ids = [row["scene_id"] for row in rows]
        else:
            matrix = self._dependency_matrix_cache.get_or_build(
                root_id=root_id,
                branch_id=branch_id,
                builder=lambda: self._build_dependency_matrix(root_id),
            )
            matrix = await matrix if inspect.isawaitable(matrix) else matrix
            impacted_scene_ids = matrix.get_impacted_scenes(entity_ids)
            impacted_scene_ids = (
                matrix.filter_scenes_after(impacted_scene_ids, min_scene_seq=scene_seq)
                if isinstance(matrix, DependencyMatrix)
                else impacted_scene_ids
            )

        severity = self._calculate_severity(state_changes)
        results: list[dict[str, Any]] = []
        for impacted_scene_id in impacted_scene_ids:
            results.append(
                {
                    "scene_id": impacted_scene_id,
                    "severity": severity,
                    "reason": self._build_reason(
                        impacted_scene_id,
                        state_changes,
                    ),
                }
            )
        return results

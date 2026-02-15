"""World snapshot manager backed by Memgraph."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.storage.schema import WorldSnapshot
from app.storage.temporal_edge import TemporalEdgeManager


class SnapshotManager:
    def __init__(self, db: Any) -> None:
        self._db = db
        self._temporal = TemporalEdgeManager(db)

    def should_create_snapshot(self, *, scene_seq: int) -> bool:
        return scene_seq > 0 and scene_seq % 10 == 0

    def create_snapshot_if_needed(
        self,
        *,
        scene_version_id: str,
        branch_id: str,
        scene_seq: int,
    ) -> WorldSnapshot | None:
        if not self.should_create_snapshot(scene_seq=scene_seq):
            return None
        existing = next(
            self._db.execute_and_fetch(
                "MATCH (s:WorldSnapshot {branch_id: $branch_id, scene_seq: $scene_seq}) "
                "RETURN s LIMIT 1;",
                {"branch_id": branch_id, "scene_seq": scene_seq},
            ),
            None,
        )
        if existing is not None:
            snapshot = WorldSnapshot(**existing["s"]._properties)
            self._db.execute(
                "MATCH (sv:SceneVersion {id: $scene_version_id}), "
                "(s:WorldSnapshot {id: $snapshot_id}) "
                "MERGE (sv)-[:ESTABLISHES_STATE]->(s);",
                {"scene_version_id": snapshot.scene_version_id, "snapshot_id": snapshot.id},
            )
            return snapshot

        entity_states, relations = self._temporal.build_world_state_with_relations(
            branch_id=branch_id,
            scene_seq=scene_seq,
        )
        snapshot = WorldSnapshot(
            id=str(uuid4()),
            scene_version_id=scene_version_id,
            branch_id=branch_id,
            scene_seq=scene_seq,
            entity_states=entity_states,
            relations=relations,
        )
        self._db.execute(
            "CREATE (s:WorldSnapshot) "
            "SET s.id = $id, "
            "s.scene_version_id = $scene_version_id, "
            "s.branch_id = $branch_id, "
            "s.scene_seq = $scene_seq, "
            "s.entity_states = $entity_states, "
            "s.relations = $relations;",
            {
                "id": snapshot.id,
                "scene_version_id": snapshot.scene_version_id,
                "branch_id": snapshot.branch_id,
                "scene_seq": snapshot.scene_seq,
                "entity_states": snapshot.entity_states,
                "relations": snapshot.relations,
            },
        )
        self._db.execute(
            "MATCH (sv:SceneVersion {id: $scene_version_id}), "
            "(s:WorldSnapshot {id: $snapshot_id}) "
            "MERGE (sv)-[:ESTABLISHES_STATE]->(s);",
            {"scene_version_id": snapshot.scene_version_id, "snapshot_id": snapshot.id},
        )
        return snapshot

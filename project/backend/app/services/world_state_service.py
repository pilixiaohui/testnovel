"""World state service for time-travel queries and snapshot creation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.storage.snapshot import SnapshotManager
from app.storage.temporal_edge import TemporalEdgeManager


class WorldStateService:
    def __init__(self, db: Any) -> None:
        self._db = db
        self._temporal = TemporalEdgeManager(db)
        self._snapshots = SnapshotManager(db)

    def _get_latest_snapshot(
        self,
        *,
        branch_id: str,
        scene_seq: int,
    ) -> dict[str, Any] | None:
        record = next(
            self._db.execute_and_fetch(
                "MATCH (s:WorldSnapshot {branch_id: $branch_id}) "
                "WHERE s.scene_seq <= $scene_seq "
                "RETURN s ORDER BY s.scene_seq DESC LIMIT 1;",
                {"branch_id": branch_id, "scene_seq": scene_seq},
            ),
            None,
        )
        if record is None:
            return None
        return record["s"]._properties

    def upsert_relation(
        self,
        *,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        tension: int,
        scene_seq: int,
        branch_id: str,
        scene_version_id: str | None = None,
    ) -> None:
        self._temporal.upsert_relation(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            tension=tension,
            scene_seq=scene_seq,
            branch_id=branch_id,
        )
        self._snapshots.create_snapshot_if_needed(
            scene_version_id=scene_version_id or str(uuid4()),
            branch_id=branch_id,
            scene_seq=scene_seq,
        )

    def build_world_state(
        self,
        *,
        branch_id: str,
        scene_seq: int,
    ) -> dict[str, dict[str, Any]]:
        snapshot = self._get_latest_snapshot(branch_id=branch_id, scene_seq=scene_seq)
        if snapshot is None or snapshot.get("relations") is None:
            return self._temporal.build_world_state(
                branch_id=branch_id,
                scene_seq=scene_seq,
            )
        world_state = {
            entity_id: dict(states)
            for entity_id, states in snapshot["entity_states"].items()
        }
        if snapshot["scene_seq"] < scene_seq:
            records = self._db.execute_and_fetch(
                "MATCH (from:Entity {branch_id: $branch_id})"
                "-[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
                "WHERE r.start_scene_seq > $start_seq AND r.start_scene_seq <= $scene_seq "
                "RETURN from.id AS from_id, to.id AS to_id, r.relation_type AS relation_type, "
                "r.tension AS tension "
                "ORDER BY r.start_scene_seq ASC, from.id ASC;",
                {
                    "branch_id": branch_id,
                    "start_seq": snapshot["scene_seq"],
                    "scene_seq": scene_seq,
                },
            )
            for record in records:
                from_id = record["from_id"]
                relation_type = record["relation_type"]
                to_id = record["to_id"]
                world_state.setdefault(from_id, {})[relation_type] = to_id
        return world_state

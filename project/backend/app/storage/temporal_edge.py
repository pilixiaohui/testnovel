
from __future__ import annotations

from typing import Any


class TemporalEdgeManager:
    def __init__(self, db: Any) -> None:
        self._db = db

    def upsert_relation(
        self,
        *,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        tension: int,
        scene_seq: int,
        branch_id: str,
    ) -> None:
        self._db.execute(
            "MATCH (from:Entity {id: $from_entity_id})-"
            "[r:TemporalRelation {branch_id: $branch_id, relation_type: $relation_type}]->"
            "(:Entity) "
            "WHERE r.start_scene_seq < $scene_seq "
            "AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq) "
            "SET r.end_scene_seq = $scene_seq;",
            {
                "from_entity_id": from_entity_id,
                "branch_id": branch_id,
                "relation_type": relation_type,
                "scene_seq": scene_seq,
            },
        )
        self._db.execute(
            "MATCH (from:Entity {id: $from_entity_id}), (to:Entity {id: $to_entity_id}) "
            "CREATE (from)-[:TemporalRelation {relation_type: $relation_type, tension: $tension, "
            "start_scene_seq: $scene_seq, end_scene_seq: NULL, branch_id: $branch_id}]->(to);",
            {
                "from_entity_id": from_entity_id,
                "to_entity_id": to_entity_id,
                "relation_type": relation_type,
                "tension": tension,
                "scene_seq": scene_seq,
                "branch_id": branch_id,
            },
        )

    def query_relations_at_scene(
        self,
        *,
        from_entity_id: str,
        branch_id: str,
        scene_seq: int,
    ) -> list[dict[str, Any]]:
        records = self._db.execute_and_fetch(
            "MATCH (from:Entity {id: $from_entity_id, branch_id: $branch_id})-"
            "[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
            "WHERE r.start_scene_seq <= $scene_seq "
            "AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq) "
            "RETURN to.id AS to_id, r.relation_type AS relation_type "
            "ORDER BY r.start_scene_seq DESC;",
            {
                "from_entity_id": from_entity_id,
                "branch_id": branch_id,
                "scene_seq": scene_seq,
            },
        )
        return [
            {"to_entity_id": record["to_id"], "relation_type": record["relation_type"]}
            for record in records
        ]

    def _active_relation_records(
        self,
        *,
        branch_id: str,
        scene_seq: int,
        root_id: str | None = None,
    ):
        params: dict[str, Any] = {"branch_id": branch_id, "scene_seq": scene_seq}
        if root_id is None:
            match = (
                "MATCH (from:Entity {branch_id: $branch_id})"
                "-[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
            )
        else:
            params["root_id"] = root_id
            match = (
                "MATCH (from:Entity {root_id: $root_id, branch_id: $branch_id})"
                "-[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
            )
        return self._db.execute_and_fetch(
            f"{match}"
            "WHERE r.start_scene_seq <= $scene_seq "
            "AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq) "
            "RETURN from.id AS from_id, r.relation_type AS relation_type, "
            "to.id AS to_id, r.tension AS tension "
            "ORDER BY from.id ASC, r.start_scene_seq DESC;",
            params,
        )

    def build_world_state(
        self,
        *,
        branch_id: str,
        scene_seq: int,
        root_id: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        records = self._active_relation_records(
            branch_id=branch_id,
            scene_seq=scene_seq,
            root_id=root_id,
        )
        world_state: dict[str, dict[str, Any]] = {}
        for record in records:
            from_id = record["from_id"]
            relation_type = record["relation_type"]
            to_id = record["to_id"]
            entity_state = world_state.setdefault(from_id, {})
            if relation_type in entity_state:
                raise ValueError(
                    "multiple active relations detected for "
                    f"from_entity_id={from_id}, relation_type={relation_type}"
                )
            entity_state[relation_type] = to_id
        return world_state

    def build_world_state_with_relations(
        self,
        *,
        branch_id: str,
        scene_seq: int,
        root_id: str | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        records = self._active_relation_records(
            branch_id=branch_id,
            scene_seq=scene_seq,
            root_id=root_id,
        )
        world_state: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []
        for record in records:
            from_id = record["from_id"]
            relation_type = record["relation_type"]
            to_id = record["to_id"]
            entity_state = world_state.setdefault(from_id, {})
            if relation_type in entity_state:
                raise ValueError(
                    "multiple active relations detected for "
                    f"from_entity_id={from_id}, relation_type={relation_type}"
                )
            entity_state[relation_type] = to_id
            relations.append(
                {
                    "from_entity_id": from_id,
                    "to_entity_id": to_id,
                    "relation_type": relation_type,
                    "tension": record["tension"],
                }
            )
        return world_state, relations

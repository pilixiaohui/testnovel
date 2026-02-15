from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from neo4j import GraphDatabase


@dataclass(frozen=True)
class EntityState:
    state_id: str
    entity_id: str
    start_scene_seq: int
    end_scene_seq: int
    semantic_states: dict[str, Any]


@dataclass(frozen=True)
class WorldSnapshot:
    snapshot_id: str
    scene_seq: int
    world_state: dict[str, dict[str, Any]]


class MemgraphWorldStateStorage:
    """Memgraph 存储：时序状态 + world_state(scene_seq) 查询 + snapshot。

    注意：这是 M2-T3 的最小闭环实现；不与现有 Kùzu GraphStorage 做兜底/回退。
    """

    def __init__(
        self,
        *,
        uri: str,
        username: str = "",
        password: str = "",
        connection_timeout_seconds: float = 3.0,
    ) -> None:
        self._driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=connection_timeout_seconds,
        )
        # Fast-fail: validate the connection early so callers don't proceed with a broken storage.
        with self._driver.session() as session:
            session.run("RETURN 1 AS ok").single()

    def close(self) -> None:
        self._driver.close()

    def clear_all(self) -> None:
        """测试辅助：清空整个 Memgraph。"""
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def add_entity_state(
        self,
        *,
        entity_id: str,
        semantic_states: dict[str, Any],
        start_scene_seq: int,
        end_scene_seq: int,
    ) -> EntityState:
        if start_scene_seq > end_scene_seq:
            raise ValueError("start_scene_seq must be <= end_scene_seq")

        state_id = str(uuid4())
        semantic_states_json = json.dumps(
            semantic_states, separators=(",", ":"), ensure_ascii=False, sort_keys=True
        )

        cypher = (
            "MERGE (e:Entity {entity_id: $entity_id}) "
            "CREATE (s:State {state_id: $state_id, semantic_states_json: $semantic_states_json}) "
            "CREATE (e)-[r:HAS_STATE {start_scene_seq: $start_scene_seq, end_scene_seq: $end_scene_seq}]->(s) "
            "RETURN e.entity_id AS entity_id, s.state_id AS state_id, "
            "r.start_scene_seq AS start_scene_seq, r.end_scene_seq AS end_scene_seq, "
            "s.semantic_states_json AS semantic_states_json"
        )
        with self._driver.session() as session:
            record = session.run(
                cypher,
                entity_id=entity_id,
                state_id=state_id,
                semantic_states_json=semantic_states_json,
                start_scene_seq=start_scene_seq,
                end_scene_seq=end_scene_seq,
            ).single()
        if record is None:
            raise RuntimeError("failed to create entity state")

        return EntityState(
            state_id=record["state_id"],
            entity_id=record["entity_id"],
            start_scene_seq=int(record["start_scene_seq"]),
            end_scene_seq=int(record["end_scene_seq"]),
            semantic_states=json.loads(record["semantic_states_json"]),
        )

    def list_entity_states(self, *, entity_id: str) -> list[EntityState]:
        cypher = (
            "MATCH (e:Entity {entity_id: $entity_id})-[r:HAS_STATE]->(s:State) "
            "RETURN e.entity_id AS entity_id, s.state_id AS state_id, "
            "r.start_scene_seq AS start_scene_seq, r.end_scene_seq AS end_scene_seq, "
            "s.semantic_states_json AS semantic_states_json "
            "ORDER BY r.start_scene_seq ASC, r.end_scene_seq ASC, s.state_id ASC"
        )
        with self._driver.session() as session:
            records = list(session.run(cypher, entity_id=entity_id))

        return [
            EntityState(
                state_id=record["state_id"],
                entity_id=record["entity_id"],
                start_scene_seq=int(record["start_scene_seq"]),
                end_scene_seq=int(record["end_scene_seq"]),
                semantic_states=json.loads(record["semantic_states_json"]),
            )
            for record in records
        ]

    def get_world_state(self, *, scene_seq: int) -> dict[str, dict[str, Any]]:
        cypher = (
            "MATCH (e:Entity)-[r:HAS_STATE]->(s:State) "
            "WHERE r.start_scene_seq <= $scene_seq AND r.end_scene_seq >= $scene_seq "
            "RETURN e.entity_id AS entity_id, s.semantic_states_json AS semantic_states_json "
            "ORDER BY e.entity_id ASC, r.start_scene_seq ASC, r.end_scene_seq ASC, s.state_id ASC"
        )
        with self._driver.session() as session:
            records = list(session.run(cypher, scene_seq=scene_seq))

        world_state: dict[str, dict[str, Any]] = {}
        for record in records:
            entity_id = record["entity_id"]
            if entity_id in world_state:
                # Fast-fail: overlapping states make world_state ambiguous.
                raise ValueError(f"overlapping states detected for entity_id={entity_id}")
            world_state[entity_id] = json.loads(record["semantic_states_json"])
        return world_state

    def create_snapshot(self, *, scene_seq: int) -> WorldSnapshot:
        snapshot_id = str(uuid4())
        world_state = self.get_world_state(scene_seq=scene_seq)
        world_state_json = json.dumps(
            world_state, separators=(",", ":"), ensure_ascii=False, sort_keys=True
        )

        cypher = (
            "CREATE (s:Snapshot {snapshot_id: $snapshot_id, scene_seq: $scene_seq, world_state_json: $world_state_json}) "
            "RETURN s.snapshot_id AS snapshot_id, s.scene_seq AS scene_seq, s.world_state_json AS world_state_json"
        )
        with self._driver.session() as session:
            record = session.run(
                cypher,
                snapshot_id=snapshot_id,
                scene_seq=scene_seq,
                world_state_json=world_state_json,
            ).single()
        if record is None:
            raise RuntimeError("failed to create snapshot")

        return WorldSnapshot(
            snapshot_id=record["snapshot_id"],
            scene_seq=int(record["scene_seq"]),
            world_state=json.loads(record["world_state_json"]),
        )

    def get_snapshot(self, *, snapshot_id: str) -> WorldSnapshot:
        cypher = (
            "MATCH (s:Snapshot {snapshot_id: $snapshot_id}) "
            "RETURN s.snapshot_id AS snapshot_id, s.scene_seq AS scene_seq, s.world_state_json AS world_state_json"
        )
        with self._driver.session() as session:
            record = session.run(cypher, snapshot_id=snapshot_id).single()
        if record is None:
            raise ValueError(f"snapshot not found: snapshot_id={snapshot_id}")

        return WorldSnapshot(
            snapshot_id=record["snapshot_id"],
            scene_seq=int(record["scene_seq"]),
            world_state=json.loads(record["world_state_json"]),
        )

"""Memgraph storage adapter built on GQLAlchemy."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import threading
import time
from typing import Any, Iterable, Iterator, Sequence, TypeVar
from uuid import uuid4

from gqlalchemy import Memgraph
from gqlalchemy.connection import Connection

from app.constants import DEFAULT_BRANCH_ID
from app.storage.schema import (
    Act,
    Branch,
    BranchHead,
    Chapter,
    CharacterAgentState,
    Commit,
    Entity,
    Root,
    SceneOrigin,
    SceneVersion,
    SimulationLog,
    StoryAnchor,
    Subplot,
    WorldSnapshot,
)
from app.storage.snapshot import SnapshotManager
from app.storage.temporal_edge import TemporalEdgeManager

NodeType = TypeVar("NodeType")

VALID_ANCHOR_TYPES = {"inciting_incident", "midpoint", "climax", "resolution"}
VALID_ANCHOR_CONSTRAINTS = {"hard", "soft", "flexible"}
AGENT_MEMORY_LIMIT = 80


class _ValidatedMemgraph(Memgraph):  # pragma: no cover
    def save_node(self, node: object):  # type: ignore[override]
        node_id = getattr(node, "id", None)
        if not node_id:
            raise ValueError("node id is required")
        return super().save_node(node)


def _get_positive_int_env(name: str, default: int) -> int:  # pragma: no cover
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _get_positive_float_env(name: str, default: float) -> float:  # pragma: no cover
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _read_character_state(semantic_states: Any, field: str) -> str:
    if not isinstance(semantic_states, dict):
        return ""
    value = semantic_states.get(field)
    if not isinstance(value, str):
        return ""
    return value


def _build_character_snapshot(
    *,
    entity_id: str,
    name: Any,
    semantic_states: Any,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "name": name,
        "ambition": _read_character_state(semantic_states, "ambition"),
        "conflict": _read_character_state(semantic_states, "conflict"),
        "epiphany": _read_character_state(semantic_states, "epiphany"),
        "voice_dna": _read_character_state(semantic_states, "voice_dna"),
    }


class _MemgraphConnectionPool:  # pragma: no cover
    def __init__(
        self,
        db: Memgraph,
        *,
        min_size: int,
        max_size: int,
        acquire_timeout: float,
        idle_timeout: float,
    ) -> None:
        if min_size <= 0:
            raise ValueError("memgraph pool min_size must be > 0")
        if max_size < min_size:
            raise ValueError("memgraph pool max_size must be >= min_size")
        if acquire_timeout <= 0:
            raise ValueError("memgraph pool acquire_timeout must be > 0")
        if idle_timeout <= 0:
            raise ValueError("memgraph pool idle_timeout must be > 0")
        self._db = db
        self._min_size = min_size
        self._max_size = max_size
        self._acquire_timeout = acquire_timeout
        self._idle_timeout = idle_timeout
        self._pool: list[tuple[Connection, float]] = []
        self._in_use = 0
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return
        for _ in range(self._min_size):
            self._pool.append((self._db.new_connection(), time.monotonic()))
        self._initialized = True

    @staticmethod
    def _close_connection(conn: Connection) -> None:
        conn._connection.close()

    def _pop_available(self) -> Connection | None:
        now = time.monotonic()
        while self._pool:
            conn, last_used = self._pool.pop()
            if now - last_used > self._idle_timeout:
                self._close_connection(conn)
                continue
            return conn
        return None

    def acquire(self) -> Connection:
        self._initialize()
        deadline = time.monotonic() + self._acquire_timeout
        while True:
            conn = self._pop_available()
            if conn is not None:
                self._in_use += 1
                return conn
            if self._in_use < self._max_size:
                self._in_use += 1
                return self._db.new_connection()
            if time.monotonic() >= deadline:
                raise RuntimeError("memgraph connection pool exhausted")
            time.sleep(0.05)

    def release(self, conn: Connection) -> None:
        if self._in_use <= 0:
            raise RuntimeError("memgraph connection pool release underflow")
        self._in_use -= 1
        self._pool.append((conn, time.monotonic()))

    def close(self) -> None:
        if self._in_use != 0:
            raise RuntimeError("memgraph connection pool closed with active sessions")
        for conn, _ in self._pool:
            self._close_connection(conn)
        self._pool.clear()


class MemgraphStorage:  # pragma: no cover
    _cache_lock = threading.Lock()
    _entity_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    _character_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    _relation_min_seq_cache: dict[tuple[str, str], int | None] = {}
    _scene_relation_cache: dict[
        tuple[str, str, int],
        tuple[dict[str, dict[str, Any]], list[dict[str, Any]]],
    ] = {}

    def __init__(self, *, host: str | None = None, port: int | None = None) -> None:
        resolved_host = host or os.getenv("MEMGRAPH_HOST")
        if not resolved_host:
            raise ValueError("MEMGRAPH_HOST is required")
        resolved_port = port
        if resolved_port is None:
            raw_port = os.getenv("MEMGRAPH_PORT")
            if not raw_port:
                raise ValueError("MEMGRAPH_PORT is required")
            try:
                resolved_port = int(raw_port)
            except ValueError as exc:
                raise ValueError("MEMGRAPH_PORT must be an integer") from exc
            if resolved_port <= 0:
                raise ValueError("MEMGRAPH_PORT must be > 0")
        self.db = _ValidatedMemgraph(host=resolved_host, port=resolved_port)
        pool_min = _get_positive_int_env("MEMGRAPH_POOL_MIN", 10)
        pool_max = _get_positive_int_env("MEMGRAPH_POOL_MAX", 100)
        pool_acquire_timeout = _get_positive_float_env(
            "MEMGRAPH_POOL_ACQUIRE_TIMEOUT", 30.0
        )
        pool_idle_timeout = _get_positive_float_env("MEMGRAPH_POOL_IDLE_TIMEOUT", 300.0)
        self._pool = _MemgraphConnectionPool(
            self.db,
            min_size=pool_min,
            max_size=pool_max,
            acquire_timeout=pool_acquire_timeout,
            idle_timeout=pool_idle_timeout,
        )

    def close(self) -> None:
        self._pool.close()
        cached = self.db._cached_connection
        if cached is None:
            return
        cached._connection.close()

    @contextmanager
    def session(self) -> Iterator[Connection]:
        conn = self._pool.acquire()
        try:
            yield conn
        finally:
            self._pool.release(conn)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        with self.session() as conn:
            conn.execute("BEGIN")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _branch_node_id(root_id: str, branch_id: str) -> str:
        return f"{root_id}:{branch_id}"

    @staticmethod
    def _branch_head_id(root_id: str, branch_id: str) -> str:
        return f"{root_id}:{branch_id}:head"

    def _get_branch_by_key(self, root_id: str, branch_id: str) -> Branch | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (b:Branch {root_id: $root_id, branch_id: $branch_id}) RETURN b LIMIT 1;",
                {"root_id": root_id, "branch_id": branch_id},
            ),
            None,
        )
        if result is None:
            return None
        return Branch(**result["b"]._properties)

    def _get_branch_head_by_key(self, root_id: str, branch_id: str) -> BranchHead | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (h:BranchHead {root_id: $root_id, branch_id: $branch_id}) RETURN h LIMIT 1;",
                {"root_id": root_id, "branch_id": branch_id},
            ),
            None,
        )
        if result is None:
            return None
        return BranchHead(**result["h"]._properties)

    def _require_root_node(self, root_id: str) -> Root:
        root = self.get_root(root_id)
        if root is None:
            raise KeyError(f"root not found: {root_id}")
        return root

    def _require_branch_node(self, root_id: str, branch_id: str) -> Branch:
        branch = self._get_branch_by_key(root_id, branch_id)
        if branch is None:
            raise KeyError(f"branch not found: {branch_id}")
        return branch

    def _require_scene_origin(self, scene_origin_id: str) -> SceneOrigin:
        scene_origin = self.get_scene_origin(scene_origin_id)
        if scene_origin is None:
            raise KeyError(f"scene origin not found: {scene_origin_id}")
        return scene_origin

    def _invalidate_entity_cache(
        self, *, root_id: str | None = None, branch_id: str | None = None
    ) -> None:
        cls = self.__class__
        with cls._cache_lock:
            if root_id is None or branch_id is None:
                cls._entity_cache.clear()
                cls._character_cache.clear()
                return
            cls._entity_cache.pop((root_id, branch_id), None)
            cls._character_cache.pop((root_id, branch_id), None)

    def _invalidate_relation_cache(
        self, *, root_id: str | None = None, branch_id: str | None = None
    ) -> None:
        cls = self.__class__
        with cls._cache_lock:
            if root_id is None or branch_id is None:
                cls._relation_min_seq_cache.clear()
                cls._scene_relation_cache.clear()
                return
            cache_key = (root_id, branch_id)
            cls._relation_min_seq_cache.pop(cache_key, None)
            keys_to_delete = [
                key
                for key in cls._scene_relation_cache
                if key[0] == root_id and key[1] == branch_id
            ]
            for key in keys_to_delete:
                del cls._scene_relation_cache[key]

    def _get_cached_entities(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        cache_key = (root_id, branch_id)
        cls = self.__class__
        with cls._cache_lock:
            if cache_key in cls._entity_cache:
                return cls._entity_cache[cache_key]
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        records = self.db.execute_and_fetch(
            "MATCH (e:Entity {root_id: $root_id, branch_id: $branch_id}) "
            "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type, "
            "e.tags AS tags, e.arc_status AS arc_status, e.semantic_states AS semantic_states "
            "ORDER BY e.id ASC;",
            {"root_id": root_id, "branch_id": branch_id},
        )
        entities: list[dict[str, Any]] = []
        characters: list[dict[str, Any]] = []
        for record in records:
            entity = {
                "entity_id": record["id"],
                "name": record.get("name"),
                "entity_type": record.get("entity_type"),
                "tags": record.get("tags") or [],
                "arc_status": record.get("arc_status"),
                "semantic_states": record.get("semantic_states") or {},
            }
            entities.append(entity)
            if entity.get("entity_type") == "Character":
                characters.append(
                    _build_character_snapshot(
                        entity_id=entity["entity_id"],
                        name=entity.get("name"),
                        semantic_states=entity.get("semantic_states"),
                    )
                )
        with cls._cache_lock:
            cls._entity_cache[cache_key] = entities
            cls._character_cache[cache_key] = characters
        return entities

    def _get_cached_characters(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        cache_key = (root_id, branch_id)
        cls = self.__class__
        with cls._cache_lock:
            if cache_key in cls._character_cache:
                return cls._character_cache[cache_key]
        self._get_cached_entities(root_id=root_id, branch_id=branch_id)
        with cls._cache_lock:
            return cls._character_cache.get(cache_key, [])

    def _get_relation_min_seq(self, *, root_id: str, branch_id: str) -> int | None:
        cache_key = (root_id, branch_id)
        cls = self.__class__
        with cls._cache_lock:
            if cache_key in cls._relation_min_seq_cache:
                return cls._relation_min_seq_cache[cache_key]
        result = next(
            self.db.execute_and_fetch(
                "MATCH (from:Entity {root_id: $root_id, branch_id: $branch_id})"
                "-[r:TemporalRelation {branch_id: $branch_id}]->(:Entity) "
                "RETURN min(r.start_scene_seq) AS min_seq;",
                {"root_id": root_id, "branch_id": branch_id},
            ),
            None,
        )
        if result is None or result["min_seq"] is None:
            min_seq = None
        else:
            min_seq = int(result["min_seq"])
        with cls._cache_lock:
            cls._relation_min_seq_cache[cache_key] = min_seq
        return min_seq

    def _get_scene_relations(
        self, *, root_id: str, branch_id: str, scene_seq: int
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        cache_key = (root_id, branch_id, scene_seq)
        cls = self.__class__
        with cls._cache_lock:
            if cache_key in cls._scene_relation_cache:
                return cls._scene_relation_cache[cache_key]
        min_seq = self._get_relation_min_seq(root_id=root_id, branch_id=branch_id)
        if min_seq is None or scene_seq < min_seq:
            return {}, []
        world_state, relations = TemporalEdgeManager(self.db).build_world_state_with_relations(
            branch_id=branch_id,
            scene_seq=scene_seq,
            root_id=root_id,
        )
        relations = sorted(
            relations,
            key=lambda rel: (rel["from_entity_id"], rel["relation_type"], rel["to_entity_id"]),
        )
        with cls._cache_lock:
            cls._scene_relation_cache[cache_key] = (world_state, relations)
        return world_state, relations

    def _get_latest_scene_version(self, scene_origin_id: str) -> SceneVersion | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
                "RETURN sv ORDER BY sv.id DESC LIMIT 1;",
                {"scene_origin_id": scene_origin_id},
            ),
            None,
        )
        if result is None:
            return None
        return SceneVersion(**result["sv"]._properties)

    def _get_scene_version_for_commit(
        self, *, scene_origin_id: str, commit_id: str
    ) -> SceneVersion | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id, commit_id: $commit_id}) "
                "RETURN sv LIMIT 1;",
                {"scene_origin_id": scene_origin_id, "commit_id": commit_id},
            ),
            None,
        )
        if result is None:
            return None
        return SceneVersion(**result["sv"]._properties)

    def _get_entity_by_key(self, root_id: str, branch_id: str, entity_id: str) -> Entity | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (e:Entity {id: $id, root_id: $root_id, branch_id: $branch_id}) "
                "RETURN e LIMIT 1;",
                {"id": entity_id, "root_id": root_id, "branch_id": branch_id},
            ),
            None,
        )
        if result is None:
            return None
        return Entity(**result["e"]._properties)

    def _get_latest_scene_seq(self, root_id: str) -> int:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (s:SceneOrigin {root_id: $root_id}) RETURN max(s.sequence_index) AS seq;",
                {"root_id": root_id},
            ),
            None,
        )
        if result is None or result["seq"] is None:
            return 0
        return int(result["seq"])

    def _get_scene_origin_by_seq(self, *, root_id: str, scene_seq: int) -> SceneOrigin | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (s:SceneOrigin {root_id: $root_id, sequence_index: $scene_seq}) "
                "RETURN s LIMIT 1;",
                {"root_id": root_id, "scene_seq": scene_seq},
            ),
            None,
        )
        if result is None:
            return None
        return SceneOrigin(**result["s"]._properties)

    def _get_latest_world_snapshot(
        self, *, branch_id: str, scene_seq: int
    ) -> WorldSnapshot | None:
        result = next(
            self.db.execute_and_fetch(
                "MATCH (s:WorldSnapshot {branch_id: $branch_id}) "
                "WHERE s.scene_seq <= $scene_seq "
                "RETURN s ORDER BY s.scene_seq DESC LIMIT 1;",
                {"branch_id": branch_id, "scene_seq": scene_seq},
            ),
            None,
        )
        if result is None:
            return None
        return WorldSnapshot(**result["s"]._properties)

    @staticmethod
    def _require_content_field(content: dict[str, Any], key: str) -> str:
        value = content.get(key)
        if value is None:
            raise ValueError(f"{key} is required")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{key} is required")
        return value

    def _scene_version_from_content(
        self,
        *,
        scene_origin_id: str,
        commit_id: str,
        content: dict[str, Any],
    ) -> SceneVersion:
        expected_outcome = self._require_content_field(content, "expected_outcome")
        conflict_type = self._require_content_field(content, "conflict_type")
        actual_outcome = self._require_content_field(content, "actual_outcome")
        return SceneVersion(
            id=f"{scene_origin_id}:{uuid4()}",
            scene_origin_id=scene_origin_id,
            commit_id=commit_id,
            pov_character_id=str(content.get("pov_character_id") or ""),
            status=str(content.get("status") or "draft"),
            expected_outcome=expected_outcome,
            conflict_type=conflict_type,
            actual_outcome=actual_outcome,
            summary=content.get("summary"),
            rendered_content=content.get("rendered_content"),
            logic_exception=bool(content.get("logic_exception", False)),
            logic_exception_reason=content.get("logic_exception_reason"),
            dirty=bool(content.get("dirty", False)),
            simulation_log_id=content.get("simulation_log_id"),
            is_simulated=bool(content.get("is_simulated", False)),
        )

    @staticmethod
    def _props_from(
        node: object,
        *,
        required: tuple[str, ...],
        optional: tuple[str, ...],
    ) -> dict[str, object]:
        props: dict[str, object] = {}
        for field in required:
            value = getattr(node, field, None)
            if value is None:
                raise ValueError(f"{field} is required")
            props[field] = value
        for field in optional:
            value = getattr(node, field, None)
            if value is not None:
                props[field] = value
        return props

    def _create_node(self, label: str, props: dict[str, object]) -> None:
        self.db.execute(f"CREATE (n:{label}) SET n += $props;", {"props": props})

    def _get_node(self, label: str, node_cls: type[NodeType], node_id: str) -> NodeType | None:
        result = next(
            self.db.execute_and_fetch(
                f"MATCH (n:{label} {{id: $id}}) RETURN n LIMIT 1;",
                {"id": node_id},
            ),
            None,
        )
        if result is None:
            return None
        node = result["n"]
        return node_cls(**node._properties)

    def _update_node(self, label: str, node_id: str, props: dict[str, object]) -> None:
        self.db.execute(
            f"MATCH (n:{label} {{id: $id}}) SET n += $props;",
            {"id": node_id, "props": props},
        )

    def _delete_node(self, label: str, node_id: str) -> None:
        self.db.execute(
            f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n;",
            {"id": node_id},
        )

    def _create_edge(
        self,
        *,
        from_label: str,
        from_id: str,
        rel_type: str,
        to_label: str,
        to_id: str,
    ) -> None:
        self.db.execute(
            f"MATCH (from:{from_label} {{id: $from_id}}), (to:{to_label} {{id: $to_id}}) "
            f"CREATE (from)-[:{rel_type}]->(to);",
            {"from_id": from_id, "to_id": to_id},
        )

    def _set_head_edge(self, *, branch_head_id: str, commit_id: str) -> None:
        self.db.execute(
            "MATCH (h:BranchHead {id: $head_id})-[r:HEAD]->() DELETE r;",
            {"head_id": branch_head_id},
        )
        self._create_edge(
            from_label="BranchHead",
            from_id=branch_head_id,
            rel_type="HEAD",
            to_label="Commit",
            to_id=commit_id,
        )

    def _create_parent_edge(self, commit: Commit) -> None:
        if commit.parent_id is None:
            return
        self._create_edge(
            from_label="Commit",
            from_id=commit.id,
            rel_type="PARENT",
            to_label="Commit",
            to_id=commit.parent_id,
        )

    def _create_includes_edge(self, *, commit_id: str, scene_version_id: str) -> None:
        self._create_edge(
            from_label="Commit",
            from_id=commit_id,
            rel_type="INCLUDES",
            to_label="SceneVersion",
            to_id=scene_version_id,
        )

    def _create_of_origin_edge(self, *, scene_version_id: str, scene_origin_id: str) -> None:
        self._create_edge(
            from_label="SceneVersion",
            from_id=scene_version_id,
            rel_type="OF_ORIGIN",
            to_label="SceneOrigin",
            to_id=scene_origin_id,
        )

    def _root_props(self, root: Root) -> dict[str, object]:
        return self._props_from(
            root,
            required=("id", "logline", "theme", "ending"),
            optional=("created_at",),
        )

    def _branch_props(self, branch: Branch) -> dict[str, object]:
        return self._props_from(
            branch,
            required=("id", "root_id", "branch_id"),
            optional=("parent_branch_id", "fork_scene_origin_id", "fork_commit_id"),
        )

    def _branch_head_props(self, branch_head: BranchHead) -> dict[str, object]:
        return self._props_from(
            branch_head,
            required=("id", "root_id", "branch_id", "head_commit_id", "version"),
            optional=(),
        )

    def _commit_props(self, commit: Commit) -> dict[str, object]:
        return self._props_from(
            commit,
            required=("id", "created_at", "root_id"),
            optional=("parent_id", "message", "branch_id"),
        )

    def _scene_origin_props(self, scene_origin: SceneOrigin) -> dict[str, object]:
        return self._props_from(
            scene_origin,
            required=(
                "id",
                "root_id",
                "title",
                "initial_commit_id",
                "sequence_index",
            ),
            optional=("parent_act_id", "chapter_id", "is_skeleton"),
        )

    def _scene_version_props(self, scene_version: SceneVersion) -> dict[str, object]:
        return self._props_from(
            scene_version,
            required=(
                "id",
                "scene_origin_id",
                "commit_id",
                "pov_character_id",
                "status",
                "expected_outcome",
                "conflict_type",
                "actual_outcome",
                "logic_exception",
                "dirty",
            ),
            optional=(
                "summary",
                "rendered_content",
                "logic_exception_reason",
                "simulation_log_id",
                "is_simulated",
            ),
        )

    def _entity_props(self, entity: Entity) -> dict[str, object]:
        return self._props_from(
            entity,
            required=(
                "id",
                "root_id",
                "branch_id",
                "entity_type",
                "semantic_states",
                "arc_status",
            ),
            optional=("name", "tags", "has_agent", "agent_state_id"),
        )

    def _world_snapshot_props(self, snapshot: WorldSnapshot) -> dict[str, object]:
        return self._props_from(
            snapshot,
            required=(
                "id",
                "scene_version_id",
                "branch_id",
                "scene_seq",
                "entity_states",
            ),
            optional=("relations",),
        )

    def _act_props(self, act: Act) -> dict[str, object]:
        return self._props_from(
            act,
            required=("id", "root_id", "sequence", "title", "purpose", "tone"),
            optional=(),
        )

    def _chapter_props(self, chapter: Chapter) -> dict[str, object]:
        props = self._props_from(
            chapter,
            required=("id", "act_id", "sequence", "title", "focus", "review_status"),
            optional=("pov_character_id", "rendered_content"),
        )
        review_status = props.get("review_status")
        if hasattr(review_status, "value"):
            props["review_status"] = review_status.value
        return props

    def _story_anchor_props(self, anchor: StoryAnchor) -> dict[str, object]:
        return self._props_from(
            anchor,
            required=(
                "id",
                "root_id",
                "branch_id",
                "sequence",
                "anchor_type",
                "description",
                "constraint_type",
                "required_conditions",
            ),
            optional=("deadline_scene", "achieved"),
        )

    def _character_agent_state_props(self, agent: CharacterAgentState) -> dict[str, object]:
        return self._props_from(
            agent,
            required=(
                "id",
                "character_id",
                "branch_id",
                "beliefs",
                "desires",
                "intentions",
                "memory",
                "private_knowledge",
                "last_updated_scene",
                "version",
            ),
            optional=(),
        )

    def _simulation_log_props(self, log: SimulationLog) -> dict[str, object]:
        return self._props_from(
            log,
            required=(
                "id",
                "scene_version_id",
                "round_number",
                "agent_actions",
                "dm_arbitration",
                "narrative_events",
                "sensory_seeds",
                "convergence_score",
                "drama_score",
                "info_gain",
                "stagnation_count",
            ),
            optional=(),
        )

    def _subplot_props(self, subplot: Subplot) -> dict[str, object]:
        return self._props_from(
            subplot,
            required=(
                "id",
                "root_id",
                "branch_id",
                "title",
                "subplot_type",
                "protagonist_id",
                "central_conflict",
                "status",
            ),
            optional=(),
        )

    def create_root(self, root: Root) -> Root:
        props = self._root_props(root)
        self._create_node("Root", props)
        return root

    def get_root(self, root_id: str) -> Root | None:
        return self._get_node("Root", Root, root_id)

    def list_roots(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        records = self.db.execute_and_fetch(
            "MATCH (r:Root) "
            "MATCH (c:Commit {root_id: r.id}) "
            "WITH r, max(c.created_at) AS updated_at "
            "RETURN r.id AS root_id, r.logline AS name, r.created_at AS created_at, updated_at AS updated_at "
            "ORDER BY updated_at DESC "
            "SKIP $offset LIMIT $limit;",
            {"limit": limit, "offset": offset},
        )
        roots: list[dict[str, Any]] = []
        for record in records:
            roots.append(
                {
                    "root_id": record.get("root_id"),
                    "name": record.get("name"),
                    "created_at": record.get("created_at"),
                    "updated_at": record.get("updated_at"),
                }
            )
        return roots

    def update_root(self, root: Root) -> Root:
        props = self._root_props(root)
        self._update_node("Root", root.id, props)
        return root

    def delete_root(self, root_id: str) -> None:
        self._delete_node("Root", root_id)
        self._invalidate_entity_cache()
        self._invalidate_relation_cache()

    def create_branch(
        self,
        branch: Branch | None = None,
        *,
        root_id: str | None = None,
        branch_id: str | None = None,
    ) -> Branch:
        if branch is not None:
            props = self._branch_props(branch)
            self._create_node("Branch", props)
            return branch
        if root_id is None or branch_id is None:
            raise TypeError("create_branch requires branch or root_id/branch_id")
        self._require_root_node(root_id)
        if self._get_branch_by_key(root_id, branch_id) is not None:
            raise ValueError(f"branch already exists: {branch_id}")
        branch_node = Branch(
            id=self._branch_node_id(root_id, branch_id),
            root_id=root_id,
            branch_id=branch_id,
            parent_branch_id=None,
            fork_scene_origin_id=None,
            fork_commit_id=None,
        )
        self._create_node("Branch", self._branch_props(branch_node))
        head_source = self._get_branch_head_by_key(root_id, DEFAULT_BRANCH_ID)
        if head_source is None:
            raise KeyError(f"branch head not found for root_id={root_id}, branch_id={DEFAULT_BRANCH_ID}")
        branch_head = BranchHead(
            id=self._branch_head_id(root_id, branch_id),
            root_id=root_id,
            branch_id=branch_id,
            head_commit_id=head_source.head_commit_id,
            version=1,
        )
        self.create_branch_head(branch_head)
        return branch_node

    def get_branch(self, branch_id: str) -> Branch | None:
        return self._get_node("Branch", Branch, branch_id)

    def update_branch(self, branch: Branch) -> Branch:
        props = self._branch_props(branch)
        self._update_node("Branch", branch.id, props)
        return branch

    def delete_branch(self, branch_id: str) -> None:
        self._delete_node("Branch", branch_id)
        self._invalidate_entity_cache()
        self._invalidate_relation_cache()

    def create_branch_head(self, branch_head: BranchHead) -> BranchHead:
        props = self._branch_head_props(branch_head)
        self._create_node("BranchHead", props)
        self._set_head_edge(branch_head_id=branch_head.id, commit_id=branch_head.head_commit_id)
        return branch_head

    def get_branch_head(self, branch_head_id: str) -> BranchHead | None:
        return self._get_node("BranchHead", BranchHead, branch_head_id)

    def update_branch_head(self, branch_head: BranchHead) -> BranchHead:
        props = self._branch_head_props(branch_head)
        self._update_node("BranchHead", branch_head.id, props)
        self._set_head_edge(branch_head_id=branch_head.id, commit_id=branch_head.head_commit_id)
        return branch_head

    def delete_branch_head(self, branch_head_id: str) -> None:
        self._delete_node("BranchHead", branch_head_id)

    def create_commit(self, commit: Commit) -> Commit:
        props = self._commit_props(commit)
        self._create_node("Commit", props)
        self._create_parent_edge(commit)
        return commit

    def get_commit(self, commit_id: str) -> Commit | None:
        return self._get_node("Commit", Commit, commit_id)

    def update_commit(self, commit: Commit) -> Commit:
        props = self._commit_props(commit)
        self._update_node("Commit", commit.id, props)
        return commit

    def delete_commit(self, commit_id: str) -> None:
        self._delete_node("Commit", commit_id)

    def create_scene_origin(
        self,
        scene_origin: SceneOrigin | None = None,
        *,
        root_id: str | None = None,
        branch_id: str | None = None,
        title: str | None = None,
        parent_act_id: str | None = None,
        content: dict[str, Any] | None = None,
    ) -> SceneOrigin | dict[str, Any]:
        if scene_origin is not None:
            props = self._scene_origin_props(scene_origin)
            self._create_node("SceneOrigin", props)
            return scene_origin
        if root_id is None or branch_id is None or title is None or content is None:
            raise TypeError("create_scene_origin requires scene_origin or root_id/branch_id/title/content")
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        commit_id = f"{root_id}:{branch_id}:{uuid4()}"
        commit = Commit(
            id=commit_id,
            parent_id=branch_head.head_commit_id,
            message="create scene origin",
            created_at=self._utc_now(),
            root_id=root_id,
            branch_id=branch_id,
        )
        self.create_commit(commit)
        sequence_index = self._get_latest_scene_seq(root_id) + 1
        scene_origin_id = str(uuid4())
        scene_origin_node = SceneOrigin(
            id=scene_origin_id,
            root_id=root_id,
            title=title,
            initial_commit_id=commit_id,
            sequence_index=sequence_index,
            parent_act_id=parent_act_id,
        )
        self._create_node("SceneOrigin", self._scene_origin_props(scene_origin_node))
        scene_version = self._scene_version_from_content(
            scene_origin_id=scene_origin_id,
            commit_id=commit_id,
            content=content,
        )
        self.create_scene_version(scene_version)
        updated_head = BranchHead(
            id=branch_head.id,
            root_id=branch_head.root_id,
            branch_id=branch_head.branch_id,
            head_commit_id=commit_id,
            version=branch_head.version + 1,
        )
        self.update_branch_head(updated_head)
        return {
            "commit_id": commit_id,
            "scene_origin_id": scene_origin_id,
            "scene_version_id": scene_version.id,
        }

    def get_scene_origin(self, scene_origin_id: str) -> SceneOrigin | None:
        return self._get_node("SceneOrigin", SceneOrigin, scene_origin_id)

    def update_scene_origin(self, scene_origin: SceneOrigin) -> SceneOrigin:
        props = self._scene_origin_props(scene_origin)
        self._update_node("SceneOrigin", scene_origin.id, props)
        return scene_origin

    def delete_scene_origin(
        self,
        scene_origin_id: str,
        *,
        root_id: str | None = None,
        branch_id: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any] | None:
        if root_id is None and branch_id is None and message is None:
            self._delete_node("SceneOrigin", scene_origin_id)
            return None
        if root_id is None or branch_id is None or message is None:
            raise TypeError("delete_scene_origin requires root_id/branch_id/message")
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        self._require_scene_origin(scene_origin_id)
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        commit_id = f"{root_id}:{branch_id}:{uuid4()}"
        commit = Commit(
            id=commit_id,
            parent_id=branch_head.head_commit_id,
            message=message,
            created_at=self._utc_now(),
            root_id=root_id,
            branch_id=branch_id,
        )
        self.create_commit(commit)
        records = list(
            self.db.execute_and_fetch(
                "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
                "RETURN sv.id AS id;",
                {"scene_origin_id": scene_origin_id},
            )
        )
        scene_version_ids = [record["id"] for record in records]
        self.db.execute(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) DETACH DELETE sv;",
            {"scene_origin_id": scene_origin_id},
        )
        self._delete_node("SceneOrigin", scene_origin_id)
        updated_head = BranchHead(
            id=branch_head.id,
            root_id=branch_head.root_id,
            branch_id=branch_head.branch_id,
            head_commit_id=commit_id,
            version=branch_head.version + 1,
        )
        self.update_branch_head(updated_head)
        return {"commit_id": commit_id, "scene_version_ids": scene_version_ids}

    def create_scene_version(self, scene_version: SceneVersion) -> SceneVersion:
        props = self._scene_version_props(scene_version)
        self._create_node("SceneVersion", props)
        self._create_includes_edge(commit_id=scene_version.commit_id, scene_version_id=scene_version.id)
        self._create_of_origin_edge(
            scene_version_id=scene_version.id, scene_origin_id=scene_version.scene_origin_id
        )
        return scene_version

    def get_scene_version(self, scene_version_id: str) -> SceneVersion | None:
        return self._get_node("SceneVersion", SceneVersion, scene_version_id)

    def update_scene_version(self, scene_version: SceneVersion) -> SceneVersion:
        props = self._scene_version_props(scene_version)
        self._update_node("SceneVersion", scene_version.id, props)
        return scene_version

    def delete_scene_version(self, scene_version_id: str) -> None:
        self._delete_node("SceneVersion", scene_version_id)

    def create_entity(
        self,
        entity: Entity | None = None,
        *,
        root_id: str | None = None,
        branch_id: str | None = None,
        name: str | None = None,
        entity_type: str | None = None,
        tags: Iterable[str] | None = None,
        arc_status: str | None = None,
        semantic_states: dict[str, Any] | None = None,
    ) -> Entity | str:
        if entity is not None:
            props = self._entity_props(entity)
            self._create_node("Entity", props)
            return entity
        if (
            root_id is None
            or branch_id is None
            or name is None
            or entity_type is None
            or semantic_states is None
        ):
            raise TypeError(
                "create_entity requires entity or root_id/branch_id/name/entity_type/semantic_states"
            )
        if arc_status is None:
            raise ValueError("arc_status is required")
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        entity_id = str(uuid4())
        entity_node = Entity(
            id=entity_id,
            root_id=root_id,
            branch_id=branch_id,
            entity_type=entity_type,
            name=name,
            tags=list(tags or []),
            semantic_states=semantic_states,
            arc_status=arc_status,
        )
        self._create_node("Entity", self._entity_props(entity_node))
        self._invalidate_entity_cache(root_id=root_id, branch_id=branch_id)
        return entity_id

    def get_entity(self, entity_id: str) -> Entity | None:
        return self._get_node("Entity", Entity, entity_id)

    def update_entity(self, entity: Entity) -> Entity:
        props = self._entity_props(entity)
        self._update_node("Entity", entity.id, props)
        self._invalidate_entity_cache(root_id=entity.root_id, branch_id=entity.branch_id)
        return entity

    def delete_entity(self, entity_id: str) -> None:
        self._delete_node("Entity", entity_id)
        self._invalidate_entity_cache()
        self._invalidate_relation_cache()

    def create_world_snapshot(self, snapshot: WorldSnapshot) -> WorldSnapshot:
        props = self._world_snapshot_props(snapshot)
        self._create_node("WorldSnapshot", props)
        return snapshot

    def get_world_snapshot(self, snapshot_id: str) -> WorldSnapshot | None:
        return self._get_node("WorldSnapshot", WorldSnapshot, snapshot_id)

    def update_world_snapshot(self, snapshot: WorldSnapshot) -> WorldSnapshot:
        props = self._world_snapshot_props(snapshot)
        self._update_node("WorldSnapshot", snapshot.id, props)
        return snapshot

    def delete_world_snapshot(self, snapshot_id: str) -> None:
        self._delete_node("WorldSnapshot", snapshot_id)

    def create_act(
        self, *, root_id: str, seq: int, title: str, purpose: str, tone: str
    ) -> dict[str, Any]:
        self._require_root_node(root_id)
        existing = next(
            self.db.execute_and_fetch(
                "MATCH (a:Act {root_id: $root_id, sequence: $seq}) RETURN a.id AS id LIMIT 1;",
                {"root_id": root_id, "seq": seq},
            ),
            None,
        )
        if existing is not None:
            raise KeyError(f"act sequence already exists: {seq}")
        act_id = f"{root_id}:act:{seq}"
        act = Act(
            id=act_id,
            root_id=root_id,
            sequence=seq,
            title=title,
            purpose=purpose,
            tone=tone,
        )
        self._create_node("Act", self._act_props(act))
        return {
            "id": act_id,
            "root_id": root_id,
            "sequence": seq,
            "title": title,
            "purpose": purpose,
            "tone": tone,
        }

    def get_act(self, act_id: str) -> Act | None:
        return self._get_node("Act", Act, act_id)

    def update_act(self, act: Act) -> Act:
        props = self._act_props(act)
        self._update_node("Act", act.id, props)
        return act

    def delete_act(self, act_id: str) -> None:
        self._delete_node("Act", act_id)

    def list_acts(self, *, root_id: str) -> list[dict[str, Any]]:
        self._require_root_node(root_id)
        records = self.db.execute_and_fetch(
            "MATCH (a:Act {root_id: $root_id}) RETURN a ORDER BY a.sequence ASC;",
            {"root_id": root_id},
        )
        acts: list[dict[str, Any]] = []
        for record in records:
            props = record["a"]._properties
            acts.append(
                {
                    "id": props.get("id"),
                    "root_id": props.get("root_id"),
                    "sequence": props.get("sequence"),
                    "title": props.get("title"),
                    "purpose": props.get("purpose"),
                    "tone": props.get("tone"),
                }
            )
        return acts

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
    ) -> dict[str, Any]:
        if self.get_act(act_id) is None:
            raise KeyError(f"act not found: {act_id}")
        existing = next(
            self.db.execute_and_fetch(
                "MATCH (c:Chapter {act_id: $act_id, sequence: $seq}) "
                "RETURN c.id AS id LIMIT 1;",
                {"act_id": act_id, "seq": seq},
            ),
            None,
        )
        if existing is not None:
            raise KeyError(f"chapter sequence already exists: {seq}")
        chapter_id = f"{act_id}:ch:{seq}"
        chapter = Chapter(
            id=chapter_id,
            act_id=act_id,
            sequence=seq,
            title=title,
            focus=focus,
            pov_character_id=pov_character_id,
            rendered_content=rendered_content,
            review_status=review_status,
        )
        self._create_node("Chapter", self._chapter_props(chapter))
        self._create_edge(
            from_label="Act",
            from_id=act_id,
            rel_type="CONTAINS_CHAPTER",
            to_label="Chapter",
            to_id=chapter_id,
        )
        return {
            "id": chapter_id,
            "act_id": act_id,
            "sequence": seq,
            "title": title,
            "focus": focus,
            "pov_character_id": pov_character_id,
            "rendered_content": rendered_content,
            "review_status": review_status,
        }

    def get_chapter(self, chapter_id: str) -> Chapter | None:
        return self._get_node("Chapter", Chapter, chapter_id)

    def update_chapter(self, chapter: Chapter) -> Chapter:
        props = self._chapter_props(chapter)
        self._update_node("Chapter", chapter.id, props)
        return chapter

    def delete_chapter(self, chapter_id: str) -> None:
        self._delete_node("Chapter", chapter_id)

    def list_chapters(self, *, act_id: str) -> list[dict[str, Any]]:
        records = self.db.execute_and_fetch(
            "MATCH (c:Chapter {act_id: $act_id}) RETURN c ORDER BY c.sequence ASC;",
            {"act_id": act_id},
        )
        chapters: list[dict[str, Any]] = []
        for record in records:
            props = record["c"]._properties
            chapters.append(
                {
                    "id": props.get("id"),
                    "act_id": props.get("act_id"),
                    "sequence": props.get("sequence"),
                    "title": props.get("title"),
                    "focus": props.get("focus"),
                    "pov_character_id": props.get("pov_character_id"),
                }
            )
        return chapters

    def link_scene_to_chapter(self, *, scene_id: str, chapter_id: str) -> None:
        self._require_scene_origin(scene_id)
        if self.get_chapter(chapter_id) is None:
            raise KeyError(f"chapter not found: {chapter_id}")
        self.db.execute(
            "MATCH (s:SceneOrigin {id: $scene_id}) SET s.chapter_id = $chapter_id;",
            {"scene_id": scene_id, "chapter_id": chapter_id},
        )
        self._create_edge(
            from_label="Chapter",
            from_id=chapter_id,
            rel_type="CONTAINS_SCENE",
            to_label="SceneOrigin",
            to_id=scene_id,
        )

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
    ) -> dict[str, Any]:
        if type not in VALID_ANCHOR_TYPES:
            raise ValueError(f"invalid anchor type: {type}")
        if constraint not in VALID_ANCHOR_CONSTRAINTS:
            raise ValueError(f"invalid anchor constraint: {constraint}")
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        existing = next(
            self.db.execute_and_fetch(
                "MATCH (a:StoryAnchor {root_id: $root_id, sequence: $seq}) "
                "RETURN a.id AS id LIMIT 1;",
                {"root_id": root_id, "seq": seq},
            ),
            None,
        )
        if existing is not None:
            raise KeyError(f"anchor sequence already exists: {seq}")
        anchor_id = f"{root_id}:anchor:{seq}"
        anchor = StoryAnchor(
            id=anchor_id,
            root_id=root_id,
            branch_id=branch_id,
            sequence=seq,
            anchor_type=type,
            description=desc,
            constraint_type=constraint,
            required_conditions=conditions,
            deadline_scene=None,
            achieved=False,
        )
        self._create_node("StoryAnchor", self._story_anchor_props(anchor))
        return {
            "id": anchor_id,
            "root_id": root_id,
            "branch_id": branch_id,
            "sequence": seq,
            "anchor_type": type,
            "description": desc,
            "constraint_type": constraint,
            "required_conditions": conditions,
            "deadline_scene": None,
            "achieved": False,
        }

    def get_anchor(self, anchor_id: str) -> StoryAnchor | None:
        return self._get_node("StoryAnchor", StoryAnchor, anchor_id)

    def update_anchor(self, anchor: StoryAnchor) -> StoryAnchor:
        props = self._story_anchor_props(anchor)
        self._update_node("StoryAnchor", anchor.id, props)
        return anchor

    def delete_anchor(self, anchor_id: str) -> None:
        self._delete_node("StoryAnchor", anchor_id)

    def mark_anchor_achieved(
        self, *, anchor_id: str, scene_version_id: str
    ) -> dict[str, Any]:
        anchor = self.get_anchor(anchor_id)
        if anchor is None:
            raise KeyError(f"anchor not found: {anchor_id}")
        if anchor.achieved:
            raise ValueError(f"anchor already achieved: {anchor_id}")
        if self.get_scene_version(scene_version_id) is None:
            raise KeyError(f"scene version not found: {scene_version_id}")
        self.db.execute(
            "MATCH (a:StoryAnchor {id: $anchor_id}) SET a.achieved = true;",
            {"anchor_id": anchor_id},
        )
        self._create_edge(
            from_label="StoryAnchor",
            from_id=anchor_id,
            rel_type="TRIGGERED_AT",
            to_label="SceneVersion",
            to_id=scene_version_id,
        )
        return {
            "id": anchor_id,
            "root_id": anchor.root_id,
            "branch_id": anchor.branch_id,
            "sequence": anchor.sequence,
            "anchor_type": anchor.anchor_type,
            "description": anchor.description,
            "constraint_type": anchor.constraint_type,
            "required_conditions": anchor.required_conditions,
            "deadline_scene": anchor.deadline_scene,
            "achieved": True,
        }

    def list_anchors(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        anchors: list[dict[str, Any]] = []
        for record in self.db.execute_and_fetch(
            "MATCH (a:StoryAnchor {root_id: $root_id, branch_id: $branch_id}) "
            "RETURN a ORDER BY a.sequence ASC;",
            {"root_id": root_id, "branch_id": branch_id},
        ):
            props = record["a"]._properties
            anchors.append(
                {
                    "id": props.get("id"),
                    "root_id": props.get("root_id"),
                    "branch_id": props.get("branch_id"),
                    "sequence": props.get("sequence"),
                    "anchor_type": props.get("anchor_type"),
                    "description": props.get("description"),
                    "constraint_type": props.get("constraint_type"),
                    "required_conditions": props.get("required_conditions"),
                    "deadline_scene": props.get("deadline_scene"),
                    "achieved": props.get("achieved"),
                }
            )
        return anchors

    def get_next_unachieved_anchor(
        self, *, root_id: str, branch_id: str
    ) -> dict[str, Any]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        anchors = self.db.execute_and_fetch(
            "MATCH (a:StoryAnchor {root_id: $root_id, branch_id: $branch_id}) "
            "WHERE a.achieved = false "
            "RETURN a ORDER BY a.sequence ASC;",
            {"root_id": root_id, "branch_id": branch_id},
        )
        for record in anchors:
            props = record["a"]._properties
            anchor_id = props.get("id")
            blocked = next(
                self.db.execute_and_fetch(
                    "MATCH (a:StoryAnchor {id: $anchor_id})-[:DEPENDS_ON]->(b:StoryAnchor) "
                    "WHERE b.achieved = false RETURN b LIMIT 1;",
                    {"anchor_id": anchor_id},
                ),
                None,
            )
            if blocked is not None:
                continue
            return {
                "id": props.get("id"),
                "root_id": props.get("root_id"),
                "branch_id": props.get("branch_id"),
                "sequence": props.get("sequence"),
                "anchor_type": props.get("anchor_type"),
                "description": props.get("description"),
                "constraint_type": props.get("constraint_type"),
                "required_conditions": props.get("required_conditions"),
                "deadline_scene": props.get("deadline_scene"),
                "achieved": props.get("achieved"),
            }
        raise KeyError("no unachieved anchors found")

    def init_character_agent(
        self,
        *,
        char_id: str,
        branch_id: str,
        initial_desires: list[dict[str, Any]],
    ) -> dict[str, Any]:
        entity = self.get_entity(char_id)
        if entity is None:
            raise KeyError(f"entity not found: {char_id}")
        if entity.has_agent or entity.agent_state_id:
            raise ValueError(f"agent already initialized for: {char_id}")
        agent_id = f"agent:{char_id}:{branch_id}"
        agent = CharacterAgentState(
            id=agent_id,
            character_id=char_id,
            branch_id=branch_id,
            beliefs=json.dumps({}),
            desires=json.dumps(initial_desires),
            intentions=json.dumps([]),
            memory=json.dumps([]),
            private_knowledge=json.dumps({}),
            last_updated_scene=0,
            version=1,
        )
        self._create_node("CharacterAgentState", self._character_agent_state_props(agent))
        self._create_edge(
            from_label="CharacterAgentState",
            from_id=agent_id,
            rel_type="AGENT_OF",
            to_label="Entity",
            to_id=char_id,
        )
        self.db.execute(
            "MATCH (e:Entity {id: $entity_id}) "
            "SET e.has_agent = true, e.agent_state_id = $agent_id;",
            {"entity_id": char_id, "agent_id": agent_id},
        )
        self._invalidate_entity_cache(root_id=entity.root_id, branch_id=entity.branch_id)
        return {"id": agent_id, "character_id": char_id, "branch_id": branch_id}

    def get_agent_state(self, agent_id: str) -> CharacterAgentState | None:
        return self._get_node("CharacterAgentState", CharacterAgentState, agent_id)

    def delete_agent_state(self, agent_id: str) -> None:
        agent = self.get_agent_state(agent_id)
        if agent is None:
            raise KeyError(f"agent state not found: {agent_id}")
        self.db.execute(
            "MATCH (e:Entity {id: $entity_id}) "
            "SET e.has_agent = false, e.agent_state_id = null;",
            {"entity_id": agent.character_id},
        )
        self._delete_node("CharacterAgentState", agent_id)
        entity = self.get_entity(agent.character_id)
        if entity is not None:
            self._invalidate_entity_cache(root_id=entity.root_id, branch_id=entity.branch_id)
        else:
            self._invalidate_entity_cache()

    def update_agent_desires(
        self, *, agent_id: str, desires: list[dict[str, Any]]
    ) -> dict[str, Any]:
        agent = self.get_agent_state(agent_id)
        if agent is None:
            raise KeyError(f"agent state not found: {agent_id}")
        if not isinstance(desires, list):
            raise ValueError("agent desires must be list")
        if agent.version is None:
            raise ValueError("agent version is required")
        new_version = agent.version + 1
        self.db.execute(
            "MATCH (a:CharacterAgentState {id: $agent_id}) "
            "SET a.desires = $desires, a.version = $version;",
            {
                "agent_id": agent_id,
                "desires": json.dumps(desires),
                "version": new_version,
            },
        )
        return {"id": agent_id, "desires": desires, "version": new_version}

    @staticmethod
    def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = MemgraphStorage._deep_merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged

    def update_agent_beliefs(
        self, *, agent_id: str, beliefs_patch: dict[str, Any]
    ) -> dict[str, Any]:
        agent = self.get_agent_state(agent_id)
        if agent is None:
            raise KeyError(f"agent state not found: {agent_id}")
        if agent.beliefs is None:
            raise ValueError("agent beliefs is required")
        if not isinstance(agent.beliefs, str):
            raise ValueError("agent beliefs must be json string")
        current = json.loads(agent.beliefs)
        if not isinstance(current, dict):
            raise ValueError("agent beliefs must be json object")
        merged = self._deep_merge_dict(current, beliefs_patch)
        if agent.version is None:
            raise ValueError("agent version is required")
        new_version = agent.version + 1
        self.db.execute(
            "MATCH (a:CharacterAgentState {id: $agent_id}) "
            "SET a.beliefs = $beliefs, a.version = $version;",
            {"agent_id": agent_id, "beliefs": json.dumps(merged), "version": new_version},
        )
        return {"id": agent_id, "beliefs": merged, "version": new_version}

    def add_agent_memory(self, *, agent_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        agent = self.get_agent_state(agent_id)
        if agent is None:
            raise KeyError(f"agent state not found: {agent_id}")
        if "importance" not in entry:
            raise ValueError("memory entry requires importance")
        if agent.memory is None:
            raise ValueError("agent memory is required")
        if not isinstance(agent.memory, str):
            raise ValueError("agent memory must be json string")
        current = json.loads(agent.memory)
        if not isinstance(current, list):
            raise ValueError("agent memory must be json list")
        updated = list(current) + [entry]
        updated.sort(key=lambda item: item["importance"], reverse=True)
        trimmed = updated[:AGENT_MEMORY_LIMIT]
        self.db.execute(
            "MATCH (a:CharacterAgentState {id: $agent_id}) SET a.memory = $memory;",
            {"agent_id": agent_id, "memory": json.dumps(trimmed)},
        )
        return {"id": agent_id, "memory": trimmed}

    def create_simulation_log(self, log: SimulationLog) -> SimulationLog:
        if self.get_scene_version(log.scene_version_id) is None:
            raise KeyError(f"scene version not found: {log.scene_version_id}")
        props = self._simulation_log_props(log)
        self._create_node("SimulationLog", props)
        self.db.execute(
            "MATCH (sv:SceneVersion {id: $scene_version_id}) "
            "SET sv.simulation_log_id = $log_id, sv.is_simulated = true;",
            {"scene_version_id": log.scene_version_id, "log_id": log.id},
        )
        return log

    def get_simulation_log(self, log_id: str) -> SimulationLog | None:
        return self._get_node("SimulationLog", SimulationLog, log_id)

    def list_simulation_logs(self, scene_id: str) -> list[SimulationLog]:
        prefix = f"sim:{scene_id}:round:"
        records = self.db.execute_and_fetch(
            "MATCH (l:SimulationLog) WHERE l.id STARTS WITH $prefix "
            "RETURN l ORDER BY l.round_number ASC;",
            {"prefix": prefix},
        )
        logs: list[SimulationLog] = []
        for record in records:
            node = record["l"]
            logs.append(SimulationLog(**node._properties))
        return logs

    def update_simulation_log(self, log: SimulationLog) -> SimulationLog:
        props = self._simulation_log_props(log)
        self._update_node("SimulationLog", log.id, props)
        return log

    def delete_simulation_log(self, log_id: str) -> None:
        log = self.get_simulation_log(log_id)
        if log is None:
            raise KeyError(f"simulation log not found: {log_id}")
        self._delete_node("SimulationLog", log_id)
        self.db.execute(
            "MATCH (sv:SceneVersion {id: $scene_version_id}) "
            "SET sv.simulation_log_id = null, sv.is_simulated = false;",
            {"scene_version_id": log.scene_version_id},
        )

    def create_subplot(self, subplot: Subplot) -> Subplot:
        self._require_root_node(subplot.root_id)
        self._require_branch_node(subplot.root_id, subplot.branch_id)
        props = self._subplot_props(subplot)
        self._create_node("Subplot", props)
        return subplot

    def get_subplot(self, subplot_id: str) -> Subplot | None:
        return self._get_node("Subplot", Subplot, subplot_id)

    def update_subplot(self, subplot: Subplot) -> Subplot:
        props = self._subplot_props(subplot)
        self._update_node("Subplot", subplot.id, props)
        return subplot

    def list_subplots(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        subplots: list[dict[str, Any]] = []
        for record in self.db.execute_and_fetch(
            "MATCH (s:Subplot {root_id: $root_id, branch_id: $branch_id}) "
            "RETURN s ORDER BY s.title ASC;",
            {"root_id": root_id, "branch_id": branch_id},
        ):
            props = record["s"]._properties
            subplots.append(
                {
                    "id": props.get("id"),
                    "root_id": props.get("root_id"),
                    "branch_id": props.get("branch_id"),
                    "title": props.get("title"),
                    "subplot_type": props.get("subplot_type"),
                    "protagonist_id": props.get("protagonist_id"),
                    "central_conflict": props.get("central_conflict"),
                    "status": props.get("status"),
                }
            )
        return subplots

    def delete_subplot(self, subplot_id: str) -> None:
        self._delete_node("Subplot", subplot_id)

    def save_snowflake(
        self,
        root: "SnowflakeRoot",
        characters: Sequence["CharacterSheet"],
        scenes: Sequence["SceneNode"],
    ) -> str:
        root_id = str(uuid4())
        created_at = self._utc_now()
        root_node = Root(
            id=root_id,
            logline=root.logline,
            theme=root.theme,
            ending=root.ending,
            created_at=created_at,
        )
        self._create_node("Root", self._root_props(root_node))
        branch_id = DEFAULT_BRANCH_ID
        branch_node = Branch(
            id=self._branch_node_id(root_id, branch_id),
            root_id=root_id,
            branch_id=branch_id,
            parent_branch_id=None,
            fork_scene_origin_id=None,
            fork_commit_id=None,
        )
        self._create_node("Branch", self._branch_props(branch_node))
        commit_id = f"{root_id}:{branch_id}:{uuid4()}"
        commit = Commit(
            id=commit_id,
            parent_id=None,
            message="initial",
            created_at=created_at,
            root_id=root_id,
            branch_id=branch_id,
        )
        self.create_commit(commit)
        branch_head = BranchHead(
            id=self._branch_head_id(root_id, branch_id),
            root_id=root_id,
            branch_id=branch_id,
            head_commit_id=commit_id,
            version=1,
        )
        self.create_branch_head(branch_head)
        for character in characters:
            entity_id = str(character.entity_id)
            entity_node = Entity(
                id=entity_id,
                root_id=root_id,
                branch_id=branch_id,
                entity_type="Character",
                name=character.name,
                tags=[],
                semantic_states={
                    "ambition": character.ambition,
                    "conflict": character.conflict,
                    "epiphany": character.epiphany,
                    "voice_dna": character.voice_dna,
                },
                arc_status="active",
            )
            self._create_node("Entity", self._entity_props(entity_node))
        for scene in scenes:
            if scene.pov_character_id is None:
                raise ValueError("scene pov_character_id is required")
            scene_origin_id = str(scene.id)
            scene_origin_node = SceneOrigin(
                id=scene_origin_id,
                root_id=root_id,
                title=scene.title,
                initial_commit_id=commit_id,
                sequence_index=scene.sequence_index,
                parent_act_id=str(scene.parent_act_id) if scene.parent_act_id else None,
            )
            self._create_node("SceneOrigin", self._scene_origin_props(scene_origin_node))
            scene_version = SceneVersion(
                id=f"{scene_origin_id}:{uuid4()}",
                scene_origin_id=scene_origin_id,
                commit_id=commit_id,
                pov_character_id=str(scene.pov_character_id),
                status="draft",
                expected_outcome=scene.expected_outcome,
                conflict_type=scene.conflict_type,
                actual_outcome=scene.actual_outcome,
                summary=None,
                rendered_content=None,
                logic_exception=scene.logic_exception,
                logic_exception_reason=None,
                dirty=scene.is_dirty,
            )
            self.create_scene_version(scene_version)
        return root_id

    def list_branches(self, *, root_id: str) -> list[str]:
        self._require_root_node(root_id)
        records = self.db.execute_and_fetch(
            "MATCH (b:Branch {root_id: $root_id}) RETURN b.branch_id AS branch_id "
            "ORDER BY b.branch_id ASC;",
            {"root_id": root_id},
        )
        return [record["branch_id"] for record in records]

    def require_branch(self, *, root_id: str, branch_id: str) -> None:
        self._require_root_node(root_id)
        if self._get_branch_by_key(root_id, branch_id) is None:
            raise KeyError(f"branch not found: {branch_id}")

    def merge_branch(self, *, root_id: str, branch_id: str) -> None:
        self._require_root_node(root_id)
        branch = self._require_branch_node(root_id, branch_id)
        parent_branch_id = branch.parent_branch_id or DEFAULT_BRANCH_ID
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        parent_head = self._get_branch_head_by_key(root_id, parent_branch_id)
        if parent_head is None:
            raise KeyError(f"branch head not found: {parent_branch_id}")
        updated_head = BranchHead(
            id=parent_head.id,
            root_id=parent_head.root_id,
            branch_id=parent_head.branch_id,
            head_commit_id=branch_head.head_commit_id,
            version=parent_head.version + 1,
        )
        self.update_branch_head(updated_head)

    def revert_branch(self, *, root_id: str, branch_id: str) -> None:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        commit = self.get_commit(branch_head.head_commit_id)
        if commit is None:
            raise KeyError(f"commit not found: {branch_head.head_commit_id}")
        target_commit_id = commit.parent_id or branch_head.head_commit_id
        updated_head = BranchHead(
            id=branch_head.id,
            root_id=branch_head.root_id,
            branch_id=branch_head.branch_id,
            head_commit_id=target_commit_id,
            version=branch_head.version + 1,
        )
        self.update_branch_head(updated_head)

    def fork_from_commit(
        self,
        *,
        root_id: str,
        source_commit_id: str,
        new_branch_id: str,
        parent_branch_id: str | None = None,
        fork_scene_origin_id: str | None = None,
    ) -> None:
        self._require_root_node(root_id)
        if self._get_branch_by_key(root_id, new_branch_id) is not None:
            raise ValueError(f"branch already exists: {new_branch_id}")
        if self.get_commit(source_commit_id) is None:
            raise KeyError(f"commit not found: {source_commit_id}")
        branch_node = Branch(
            id=self._branch_node_id(root_id, new_branch_id),
            root_id=root_id,
            branch_id=new_branch_id,
            parent_branch_id=parent_branch_id,
            fork_scene_origin_id=fork_scene_origin_id,
            fork_commit_id=source_commit_id,
        )
        self._create_node("Branch", self._branch_props(branch_node))
        branch_head = BranchHead(
            id=self._branch_head_id(root_id, new_branch_id),
            root_id=root_id,
            branch_id=new_branch_id,
            head_commit_id=source_commit_id,
            version=1,
        )
        self.create_branch_head(branch_head)

    def fork_from_scene(
        self,
        *,
        root_id: str,
        source_branch_id: str,
        scene_origin_id: str,
        new_branch_id: str,
        commit_id: str | None = None,
    ) -> None:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, source_branch_id)
        scene_origin = self._require_scene_origin(scene_origin_id)
        source_commit_id = commit_id or scene_origin.initial_commit_id
        self.fork_from_commit(
            root_id=root_id,
            source_commit_id=source_commit_id,
            new_branch_id=new_branch_id,
            parent_branch_id=source_branch_id,
            fork_scene_origin_id=scene_origin_id,
        )

    def reset_branch_head(self, *, root_id: str, branch_id: str, commit_id: str) -> None:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        if self.get_commit(commit_id) is None:
            raise KeyError(f"commit not found: {commit_id}")
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        updated_head = BranchHead(
            id=branch_head.id,
            root_id=branch_head.root_id,
            branch_id=branch_head.branch_id,
            head_commit_id=commit_id,
            version=branch_head.version + 1,
        )
        self.update_branch_head(updated_head)

    def get_branch_history(
        self, *, root_id: str, branch_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        records = self.db.execute_and_fetch(
            "MATCH (c:Commit {root_id: $root_id, branch_id: $branch_id}) "
            "RETURN c ORDER BY c.created_at DESC LIMIT $limit;",
            {"root_id": root_id, "branch_id": branch_id, "limit": limit},
        )
        history: list[dict[str, Any]] = []
        for record in records:
            props = record["c"]._properties
            history.append(
                {
                    "id": props.get("id"),
                    "parent_id": props.get("parent_id"),
                    "root_id": props.get("root_id"),
                    "created_at": props.get("created_at"),
                    "message": props.get("message"),
                }
            )
        return history

    def commit_scene(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_origin_id: str,
        content: dict[str, Any],
        message: str,
        expected_head_version: int | None = None,
    ) -> dict[str, Any]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        self._require_scene_origin(scene_origin_id)
        branch_head = self._get_branch_head_by_key(root_id, branch_id)
        if branch_head is None:
            raise KeyError(f"branch head not found: {branch_id}")
        if expected_head_version is not None and branch_head.version != expected_head_version:
            raise ValueError("branch head version mismatch")
        commit_id = f"{root_id}:{branch_id}:{uuid4()}"
        commit = Commit(
            id=commit_id,
            parent_id=branch_head.head_commit_id,
            message=message,
            created_at=self._utc_now(),
            root_id=root_id,
            branch_id=branch_id,
        )
        self.create_commit(commit)
        scene_version = self._scene_version_from_content(
            scene_origin_id=scene_origin_id,
            commit_id=commit_id,
            content=content,
        )
        self.create_scene_version(scene_version)
        updated_head = BranchHead(
            id=branch_head.id,
            root_id=branch_head.root_id,
            branch_id=branch_head.branch_id,
            head_commit_id=commit_id,
            version=branch_head.version + 1,
        )
        self.update_branch_head(updated_head)
        return {"commit_id": commit_id, "scene_version_ids": [scene_version.id]}

    def gc_orphan_commits(self, *, retention_days: int) -> dict[str, list[str]]:
        return {"deleted_commit_ids": [], "deleted_scene_version_ids": []}

    def get_root_snapshot(self, *, root_id: str, branch_id: str) -> dict[str, Any]:
        root = self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        entities = self.list_entities(root_id=root_id, branch_id=branch_id)
        characters = [
            _build_character_snapshot(
                entity_id=entity["entity_id"],
                name=entity.get("name"),
                semantic_states=entity.get("semantic_states"),
            )
            for entity in entities
            if entity.get("entity_type") == "Character"
        ]
        scenes: list[dict[str, Any]] = []
        scene_records = self.db.execute_and_fetch(
            "MATCH (s:SceneOrigin {root_id: $root_id}) RETURN s "
            "ORDER BY s.sequence_index ASC;",
            {"root_id": root_id},
        )
        for record in scene_records:
            props = record["s"]._properties
            scene_origin_id = props.get("id")
            if scene_origin_id is None:
                continue
            scene_version = self._get_latest_scene_version(scene_origin_id)
            scenes.append(
                {
                    "id": scene_origin_id,
                    "branch_id": branch_id,
                    "title": props.get("title"),
                    "sequence_index": props.get("sequence_index"),
                    "status": scene_version.status if scene_version else None,
                    "pov_character_id": scene_version.pov_character_id if scene_version else None,
                    "expected_outcome": scene_version.expected_outcome if scene_version else None,
                    "conflict_type": scene_version.conflict_type if scene_version else None,
                    "actual_outcome": scene_version.actual_outcome if scene_version else "",
                    "logic_exception": scene_version.logic_exception if scene_version else None,
                    "logic_exception_reason": scene_version.logic_exception_reason
                    if scene_version
                    else None,
                    "is_dirty": bool(scene_version.dirty) if scene_version else False,
                }
            )
        relation_records = self.db.execute_and_fetch(
            "MATCH (from:Entity {root_id: $root_id, branch_id: $branch_id})"
            "-[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
            "RETURN from.id AS from_id, to.id AS to_id, "
            "r.relation_type AS relation_type, r.tension AS tension "
            "ORDER BY from_id ASC, to_id ASC;",
            {"root_id": root_id, "branch_id": branch_id},
        )
        relations = [
            {
                "from_entity_id": record["from_id"],
                "to_entity_id": record["to_id"],
                "relation_type": record["relation_type"],
                "tension": record["tension"],
            }
            for record in relation_records
        ]
        return {
            "root_id": root_id,
            "branch_id": branch_id,
            "logline": root.logline,
            "theme": root.theme,
            "ending": root.ending,
            "characters": characters,
            "scenes": scenes,
            "relations": relations,
        }

    def list_entities(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        return self._get_cached_entities(root_id=root_id, branch_id=branch_id)

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
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        if self._get_entity_by_key(root_id, branch_id, from_entity_id) is None:
            raise KeyError(f"entity not found: {from_entity_id}")
        if self._get_entity_by_key(root_id, branch_id, to_entity_id) is None:
            raise KeyError(f"entity not found: {to_entity_id}")
        scene_seq = self._get_latest_scene_seq(root_id)
        TemporalEdgeManager(self.db).upsert_relation(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            tension=tension,
            scene_seq=scene_seq,
            branch_id=branch_id,
        )
        snapshots = SnapshotManager(self.db)
        if snapshots.should_create_snapshot(scene_seq=scene_seq):
            scene_origin = self._get_scene_origin_by_seq(root_id=root_id, scene_seq=scene_seq)
            if scene_origin is None:
                raise KeyError(f"scene origin not found for seq: {scene_seq}")
            scene_version = self._get_latest_scene_version(scene_origin.id)
            if scene_version is None:
                raise KeyError(f"scene version not found: {scene_origin.id}")
            snapshots.create_snapshot_if_needed(
                scene_version_id=scene_version.id,
                branch_id=branch_id,
                scene_seq=scene_seq,
            )
        self._invalidate_relation_cache(root_id=root_id, branch_id=branch_id)

    def _build_scene_context_state(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_seq: int,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        snapshot = self._get_latest_world_snapshot(branch_id=branch_id, scene_seq=scene_seq)
        if snapshot is None or snapshot.relations is None:
            return TemporalEdgeManager(self.db).build_world_state_with_relations(
                branch_id=branch_id,
                scene_seq=scene_seq,
                root_id=root_id,
            )
        world_state = {
            entity_id: dict(states) for entity_id, states in snapshot.entity_states.items()
        }
        relations_by_key = {
            (rel["from_entity_id"], rel["relation_type"]): dict(rel)
            for rel in snapshot.relations
        }
        if snapshot.scene_seq < scene_seq:
            records = self.db.execute_and_fetch(
                "MATCH (from:Entity {root_id: $root_id, branch_id: $branch_id})"
                "-[r:TemporalRelation {branch_id: $branch_id}]->(to:Entity) "
                "WHERE r.start_scene_seq > $start_seq AND r.start_scene_seq <= $scene_seq "
                "RETURN from.id AS from_id, to.id AS to_id, r.relation_type AS relation_type, "
                "r.tension AS tension "
                "ORDER BY r.start_scene_seq ASC, from.id ASC;",
                {
                    "root_id": root_id,
                    "branch_id": branch_id,
                    "start_seq": snapshot.scene_seq,
                    "scene_seq": scene_seq,
                },
            )
            for record in records:
                from_id = record["from_id"]
                relation_type = record["relation_type"]
                to_id = record["to_id"]
                world_state.setdefault(from_id, {})[relation_type] = to_id
                relations_by_key[(from_id, relation_type)] = {
                    "from_entity_id": from_id,
                    "to_entity_id": to_id,
                    "relation_type": relation_type,
                    "tension": record["tension"],
                }
        relations = sorted(
            relations_by_key.values(),
            key=lambda rel: (rel["from_entity_id"], rel["relation_type"], rel["to_entity_id"]),
        )
        return world_state, relations

    def get_scene_context(self, *, scene_id: str, branch_id: str) -> dict[str, Any]:
        scene_record = next(
            self.db.execute_and_fetch(
                "MATCH (s:SceneOrigin {id: $scene_id}) "
                "MATCH (b:Branch {root_id: s.root_id, branch_id: $branch_id}) "
                "OPTIONAL MATCH (sv:SceneVersion {scene_origin_id: s.id}) "
                "WITH s, sv ORDER BY sv.id DESC "
                "WITH s, collect(sv)[0] AS sv "
                "OPTIONAL MATCH (prev:SceneOrigin {root_id: s.root_id, "
                "sequence_index: s.sequence_index - 1}) "
                "OPTIONAL MATCH (next:SceneOrigin {root_id: s.root_id, "
                "sequence_index: s.sequence_index + 1}) "
                "RETURN s.root_id AS root_id, s.sequence_index AS scene_seq, "
                "sv.expected_outcome AS expected_outcome, sv.summary AS summary, "
                "prev.id AS prev_scene_id, next.id AS next_scene_id;",
                {"scene_id": scene_id, "branch_id": branch_id},
            ),
            None,
        )
        if scene_record is None:
            raise KeyError(f"scene context not found: {scene_id}")
        if scene_record["expected_outcome"] is None:
            raise KeyError(f"scene version not found: {scene_id}")
        root_id = scene_record["root_id"]
        scene_seq = scene_record["scene_seq"]
        entities = self._get_cached_entities(root_id=root_id, branch_id=branch_id)
        characters = self._get_cached_characters(root_id=root_id, branch_id=branch_id)
        world_state, relations = self._get_scene_relations(
            root_id=root_id,
            branch_id=branch_id,
            scene_seq=scene_seq,
        )
        return {
            "root_id": root_id,
            "branch_id": branch_id,
            "expected_outcome": scene_record["expected_outcome"],
            "semantic_states": world_state,
            "summary": scene_record.get("summary") or "",
            "scene_entities": entities,
            "characters": characters,
            "relations": relations,
            "prev_scene_id": scene_record.get("prev_scene_id"),
            "next_scene_id": scene_record.get("next_scene_id"),
        }


    def diff_scene_versions(
        self, *, scene_origin_id: str, from_commit_id: str, to_commit_id: str
    ) -> dict[str, dict[str, Any]]:
        from_version = self._get_scene_version_for_commit(
            scene_origin_id=scene_origin_id, commit_id=from_commit_id
        )
        to_version = self._get_scene_version_for_commit(
            scene_origin_id=scene_origin_id, commit_id=to_commit_id
        )
        if from_version is None:
            raise KeyError(f"scene version not found for commit: {from_commit_id}")
        if to_version is None:
            raise KeyError(f"scene version not found for commit: {to_commit_id}")
        diff: dict[str, dict[str, Any]] = {}
        fields = (
            "expected_outcome",
            "conflict_type",
            "actual_outcome",
            "summary",
            "rendered_content",
        )
        for field in fields:
            before = getattr(from_version, field, None)
            after = getattr(to_version, field, None)
            if before != after:
                diff[field] = {"from": before, "to": after}
        return diff

    def save_scene_render(self, *, scene_id: str, branch_id: str, content: str) -> None:
        self._require_scene_origin(scene_id)
        scene_version = self._get_latest_scene_version(scene_id)
        if scene_version is None:
            raise KeyError(f"scene version not found: {scene_id}")
        self.db.execute(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
            "SET sv.rendered_content = $content;",
            {"scene_origin_id": scene_id, "content": content},
        )

    def complete_scene(
        self,
        *,
        scene_id: str,
        branch_id: str,
        actual_outcome: str,
        summary: str,
    ) -> None:
        self._require_scene_origin(scene_id)
        scene_version = self._get_latest_scene_version(scene_id)
        if scene_version is None:
            raise KeyError(f"scene version not found: {scene_id}")
        self.db.execute(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
            "SET sv.actual_outcome = $actual_outcome, "
            "sv.summary = $summary, "
            "sv.status = $status;",
            {
                "scene_origin_id": scene_id,
                "actual_outcome": actual_outcome,
                "summary": summary,
                "status": "committed",
            },
        )

    def mark_scene_logic_exception(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
        reason: str,
    ) -> None:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        self._require_scene_origin(scene_id)
        self.db.execute(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
            "SET sv.logic_exception = true, sv.logic_exception_reason = $reason;",
            {"scene_origin_id": scene_id, "reason": reason},
        )

    def is_scene_logic_exception(self, *, root_id: str, branch_id: str, scene_id: str) -> bool:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        scene_version = self._get_latest_scene_version(scene_id)
        if scene_version is None:
            raise KeyError(f"scene version not found: {scene_id}")
        return bool(scene_version.logic_exception)

    def mark_scene_dirty(self, *, scene_id: str, branch_id: str) -> None:
        self._require_scene_origin(scene_id)
        self.db.execute(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
            "SET sv.dirty = true;",
            {"scene_origin_id": scene_id},
        )

    def list_dirty_scenes(self, *, root_id: str, branch_id: str) -> list[str]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        records = self.db.execute_and_fetch(
            "MATCH (sv:SceneVersion {dirty: true}) "
            "MATCH (so:SceneOrigin {id: sv.scene_origin_id, root_id: $root_id}) "
            "RETURN DISTINCT sv.scene_origin_id AS scene_origin_id "
            "ORDER BY scene_origin_id ASC;",
            {"root_id": root_id},
        )
        return [record["scene_origin_id"] for record in records]

    def require_root(self, *, root_id: str, branch_id: str) -> None:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)

    def get_entity_semantic_states(
        self, *, root_id: str, branch_id: str, entity_id: str
    ) -> dict[str, Any]:
        entity = self._get_entity_by_key(root_id, branch_id, entity_id)
        if entity is None:
            raise KeyError(f"entity not found: {entity_id}")
        return entity.semantic_states or {}

    def apply_semantic_states_patch(
        self,
        *,
        root_id: str,
        branch_id: str,
        entity_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        entity = self._get_entity_by_key(root_id, branch_id, entity_id)
        if entity is None:
            raise KeyError(f"entity not found: {entity_id}")
        current = entity.semantic_states or {}
        updated = {**current, **patch}
        self.db.execute(
            "MATCH (e:Entity {id: $id, root_id: $root_id, branch_id: $branch_id}) "
            "SET e.semantic_states = $states;",
            {
                "id": entity_id,
                "root_id": root_id,
                "branch_id": branch_id,
                "states": updated,
            },
        )
        self._invalidate_entity_cache(root_id=root_id, branch_id=branch_id)
        return updated

    def apply_local_scene_fix(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
        limit: int = 3,
    ) -> list[str]:
        self._require_root_node(root_id)
        self._require_branch_node(root_id, branch_id)
        self.mark_scene_dirty(scene_id=scene_id, branch_id=branch_id)
        return [scene_id]

    def mark_future_scenes_dirty(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_id: str,
    ) -> list[str]:
        scene_origin = self._require_scene_origin(scene_id)
        self._require_branch_node(scene_origin.root_id, branch_id)
        records = self.db.execute_and_fetch(
            "MATCH (s:SceneOrigin {root_id: $root_id}) "
            "WHERE s.sequence_index > $seq "
            "RETURN s.id AS id ORDER BY s.sequence_index ASC;",
            {"root_id": scene_origin.root_id, "seq": scene_origin.sequence_index},
        )
        scene_ids = [record["id"] for record in records]
        if scene_ids:
            self.db.execute(
                "MATCH (sv:SceneVersion) WHERE sv.scene_origin_id IN $ids "
                "SET sv.dirty = true;",
                {"ids": scene_ids},
            )
        return scene_ids

    def build_logic_check_world_state(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> dict[str, Any]:
        scene_origin = self._require_scene_origin(scene_id)
        self._require_branch_node(scene_origin.root_id, branch_id)
        return TemporalEdgeManager(self.db).build_world_state(
            branch_id=branch_id,
            scene_seq=scene_origin.sequence_index,
            root_id=scene_origin.root_id,
        )

    def insert_nodes(self, nodes: list[dict]) -> None:
        for node in nodes:
            node_id = node.get("id")
            label = node.get("label")
            if not node_id:
                raise ValueError("node id is required")
            if not label:
                raise ValueError("node label is required")
            props = dict(node.get("properties", {}))
            self.db.execute(
                f"CREATE (n:{label} {{id: $id}}) SET n += $props;",
                {"id": node_id, "props": props},
            )

    def insert_edges(self, edges: list[dict]) -> None:
        for edge in edges:
            edge_id = edge.get("id")
            edge_type = edge.get("type")
            from_id = edge.get("from_id")
            to_id = edge.get("to_id")
            if not edge_id:
                raise ValueError("edge id is required")
            if not edge_type:
                raise ValueError("edge type is required")
            if not from_id or not to_id:
                raise ValueError("edge endpoints are required")
            props = dict(edge.get("properties", {}))
            self.db.execute(
                "MATCH (from {id: $from_id}), (to {id: $to_id}) "
                f"CREATE (from)-[r:{edge_type} {{id: $id}}]->(to) SET r += $props;",
                {"from_id": from_id, "to_id": to_id, "id": edge_id, "props": props},
            )

    def delete_nodes(self, node_ids: list[str]) -> None:
        self.db.execute(
            "MATCH (n) WHERE n.id IN $ids DETACH DELETE n;",
            {"ids": node_ids},
        )

    def delete_edges(self, edge_ids: list[str]) -> None:
        self.db.execute(
            "MATCH ()-[r]->() WHERE r.id IN $ids DELETE r;",
            {"ids": edge_ids},
        )

    def snapshot(self) -> dict[str, list[dict]]:
        nodes: list[dict] = []
        for record in self.db.execute_and_fetch("MATCH (n) RETURN labels(n) AS labels, n AS node;"):
            labels = record["labels"]
            if not labels:
                raise ValueError("node label is required")
            props = dict(record["node"]._properties)
            node_id = props.pop("id", None)
            if not node_id:
                raise ValueError("node id is required")
            nodes.append(
                {
                    "id": node_id,
                    "label": labels[0],
                    "properties": props,
                }
            )

        edges: list[dict] = []
        for record in self.db.execute_and_fetch(
            "MATCH (from)-[r]->(to) "
            "RETURN type(r) AS type, r AS rel, from.id AS from_id, to.id AS to_id;"
        ):
            props = dict(record["rel"]._properties)
            edge_id = props.pop("id", None)
            if not edge_id:
                raise ValueError("edge id is required")
            from_id = record["from_id"]
            to_id = record["to_id"]
            if not from_id or not to_id:
                raise ValueError("edge endpoints are required")
            edges.append(
                {
                    "id": edge_id,
                    "type": record["type"],
                    "from_id": from_id,
                    "to_id": to_id,
                    "properties": props,
                }
            )
        return {"nodes": nodes, "edges": edges}

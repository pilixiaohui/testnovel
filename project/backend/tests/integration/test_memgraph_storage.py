import importlib
import importlib.util
import os
import re
from uuid import uuid4

import pytest


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{module_path} module is missing: {exc}", pytrace=False)
    if spec is None:
        pytest.fail(f"{module_path} module is missing", pytrace=False)
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        missing = exc.name
        if missing in {"gqlalchemy", "neo4j"}:
            pytest.fail(
                f"{module_path} requires {missing} but it is missing: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        message = str(exc)
        if "gqlalchemy" in message or "neo4j" in message:
            pytest.fail(
                f"{module_path} dependency import failed: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_memgraph_storage_class():
    module = _import_module("app.storage.memgraph_storage")
    if not hasattr(module, "MemgraphStorage"):
        pytest.fail("MemgraphStorage class is missing", pytrace=False)
    return module.MemgraphStorage


def _get_root_model():
    module = _import_module("app.storage.schema")
    if not hasattr(module, "Root"):
        pytest.fail("schema.Root is missing", pytrace=False)
    return module.Root


def _get_schema_model(name: str):
    module = _import_module("app.storage.schema")
    if not hasattr(module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    return getattr(module, name)


def _get_gqlalchemy_memgraph():
    try:
        gqlalchemy = importlib.import_module("gqlalchemy")
    except ModuleNotFoundError as exc:
        pytest.fail(f"gqlalchemy is required: {exc}", pytrace=False)
    if not hasattr(gqlalchemy, "Memgraph"):
        pytest.fail("gqlalchemy.Memgraph is missing", pytrace=False)
    return gqlalchemy.Memgraph


def _get_memgraph_connection_config() -> tuple[str, int]:
    host = os.getenv("MEMGRAPH_HOST")
    if not host:
        pytest.fail("MEMGRAPH_HOST is required", pytrace=False)
    raw_port = os.getenv("MEMGRAPH_PORT")
    if not raw_port:
        pytest.fail("MEMGRAPH_PORT is required", pytrace=False)
    try:
        port = int(raw_port)
    except ValueError as exc:
        pytest.fail(f"MEMGRAPH_PORT must be an integer: {exc}", pytrace=False)
    return host, port


def _create_storage():
    memgraph_storage_cls = _get_memgraph_storage_class()
    host, port = _get_memgraph_connection_config()
    try:
        return memgraph_storage_cls(host=host, port=port)
    except Exception as exc:  # pragma: no cover - fail-fast with clear reason
        pytest.fail(
            f"failed to create MemgraphStorage (check MEMGRAPH_HOST/MEMGRAPH_PORT): {exc}",
            pytrace=False,
        )


def _assert_memgraph_connection(storage) -> None:
    if not hasattr(storage, "db"):
        pytest.fail("MemgraphStorage.db is required for Memgraph access", pytrace=False)
    if not hasattr(storage.db, "execute_and_fetch"):
        pytest.fail("MemgraphStorage.db.execute_and_fetch is missing", pytrace=False)
    try:
        result = next(storage.db.execute_and_fetch("RETURN 1 AS ok;"), None)
    except Exception as exc:  # pragma: no cover - connectivity/driver errors
        pytest.fail(f"Memgraph connection failed: {exc}", pytrace=False)
    if not result or result.get("ok") != 1:
        pytest.fail("Memgraph RETURN 1 check failed", pytrace=False)


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _require_storage_method(storage, method_name: str):
    if not hasattr(storage, method_name):
        pytest.fail(f"MemgraphStorage.{method_name} is missing", pytrace=False)
    method = getattr(storage, method_name)
    if not callable(method):
        pytest.fail(f"MemgraphStorage.{method_name} must be callable", pytrace=False)
    return method


def _get_default_branch_id():
    module = _import_module("app.constants")
    if not hasattr(module, "DEFAULT_BRANCH_ID"):
        pytest.fail("DEFAULT_BRANCH_ID is missing", pytrace=False)
    return module.DEFAULT_BRANCH_ID


def _seed_root_with_default_branch(
    storage, *, root_id: str, branch_id: str, commit_id: str
) -> None:
    root_cls = _get_schema_model("Root")
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")

    root = root_cls(
        id=root_id,
        logline="seed",
        theme="seed",
        ending="seed",
        created_at="2024-01-01T00:00:00Z",
    )
    storage.create_root(root)

    branch = branch_cls(
        id=f"{root_id}:{branch_id}",
        root_id=root_id,
        branch_id=branch_id,
        parent_branch_id=None,
        fork_scene_origin_id=None,
        fork_commit_id=None,
    )
    storage.create_branch(branch)

    commit = commit_cls(
        id=commit_id,
        parent_id=None,
        message="seed",
        created_at="2024-01-01T00:00:00Z",
        root_id=root_id,
        branch_id=branch_id,
    )
    storage.create_commit(commit)

    branch_head = branch_head_cls(
        id=f"{root_id}:{branch_id}:head",
        root_id=root_id,
        branch_id=branch_id,
        head_commit_id=commit_id,
        version=1,
    )
    storage.create_branch_head(branch_head)


def test_memgraph_storage_module_exists():
    _get_memgraph_storage_class()


def test_memgraph_storage_minimal_crud():
    memgraph_storage_cls = _get_memgraph_storage_class()
    root_cls = _get_root_model()
    memgraph_cls = _get_gqlalchemy_memgraph()

    host, port = _get_memgraph_connection_config()
    try:
        storage = memgraph_storage_cls(host=host, port=port)
    except Exception as exc:  # pragma: no cover - fail-fast with clear reason
        pytest.fail(
            f"failed to create MemgraphStorage (check MEMGRAPH_HOST/MEMGRAPH_PORT): {exc}",
            pytrace=False,
        )

    if not isinstance(storage.db, memgraph_cls):
        pytest.fail("MemgraphStorage.db is not a gqlalchemy.Memgraph instance", pytrace=False)

    root_id = f"root-{uuid4()}"
    root = root_cls(
        id=root_id,
        logline="Test logline",
        theme="Test theme",
        ending="Test ending",
    )
    required_methods = ["create_root", "get_root", "update_root", "delete_root"]
    missing = [name for name in required_methods if not hasattr(storage, name)]
    if missing:
        pytest.fail(f"MemgraphStorage missing required methods: {missing}", pytrace=False)

    try:
        storage.create_root(root)
        loaded = storage.get_root(root_id)
    except Exception as exc:  # pragma: no cover - connectivity/driver errors
        pytest.fail(f"Memgraph CRUD failed during create/get: {exc}", pytrace=False)
    assert loaded is not None
    assert loaded.id == root_id
    assert loaded.logline == "Test logline"

    root.logline = "Updated logline"
    try:
        storage.update_root(root)
        updated = storage.get_root(root_id)
    except Exception as exc:  # pragma: no cover - connectivity/driver errors
        pytest.fail(f"Memgraph CRUD failed during update/get: {exc}", pytrace=False)
    assert updated is not None
    assert updated.logline == "Updated logline"

    try:
        storage.delete_root(root_id)
        deleted = storage.get_root(root_id)
    except Exception as exc:  # pragma: no cover - connectivity/driver errors
        pytest.fail(f"Memgraph CRUD failed during delete/get: {exc}", pytrace=False)
    assert deleted is None


def test_memgraph_storage_close_releases_connection():
    memgraph_storage_cls = _get_memgraph_storage_class()
    host, port = _get_memgraph_connection_config()
    storage = memgraph_storage_cls(host=host, port=port)

    if not hasattr(storage, "close"):
        pytest.fail(
            "MemgraphStorage.close() is required for connection management",
            pytrace=False,
        )
    storage.close()


def test_memgraph_storage_phase1_crud_methods_and_roundtrip():
    storage = _create_storage()
    _assert_memgraph_connection(storage)

    required_models = [
        "Branch",
        "BranchHead",
        "Commit",
        "SceneOrigin",
        "SceneVersion",
        "Entity",
        "WorldSnapshot",
    ]
    missing_methods = []
    for model_name in required_models:
        prefix = _camel_to_snake(model_name)
        for verb in ("create", "get", "update", "delete"):
            method_name = f"{verb}_{prefix}"
            if not hasattr(storage, method_name):
                missing_methods.append(method_name)
    if missing_methods:
        pytest.fail(
            f"MemgraphStorage missing required CRUD methods: {sorted(missing_methods)}",
            pytrace=False,
        )

    root_cls = _get_schema_model("Root")
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")
    scene_origin_cls = _get_schema_model("SceneOrigin")
    scene_version_cls = _get_schema_model("SceneVersion")
    entity_cls = _get_schema_model("Entity")
    world_snapshot_cls = _get_schema_model("WorldSnapshot")

    root_id = f"root-{uuid4()}"
    branch_id = f"branch-{uuid4()}"
    commit_id = f"commit-{uuid4()}"
    scene_origin_id = f"scene-origin-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"
    entity_id = f"entity-{uuid4()}"
    snapshot_id = f"snapshot-{uuid4()}"

    try:
        root = root_cls(
            id=root_id,
            logline="logline",
            theme="theme",
            ending="ending",
            created_at="2024-01-01T00:00:00Z",
        )
    except TypeError as exc:
        pytest.fail(f"Root model fields mismatch Phase1 contract: {exc}", pytrace=False)

    storage.create_root(root)
    created_ids = [root_id]

    try:
        branch = branch_cls(
            id=branch_id,
            root_id=root_id,
            branch_id="main",
            parent_branch_id=None,
            fork_scene_origin_id=None,
            fork_commit_id=None,
        )
    except TypeError as exc:
        pytest.fail(f"Branch model fields mismatch Phase1 contract: {exc}", pytrace=False)
    storage.create_branch(branch)
    created_ids.append(branch_id)

    try:
        commit = commit_cls(
            id=commit_id,
            parent_id=None,
            message="initial",
            created_at="2024-01-01T00:00:00Z",
            root_id=root_id,
        )
    except TypeError as exc:
        pytest.fail(f"Commit model fields mismatch Phase1 contract: {exc}", pytrace=False)
    storage.create_commit(commit)
    created_ids.append(commit_id)

    try:
        branch_head = branch_head_cls(
            id=f"{root_id}:main:head",
            root_id=root_id,
            branch_id="main",
            head_commit_id=commit_id,
            version=1,
        )
    except TypeError as exc:
        pytest.fail(
            f"BranchHead model fields mismatch Phase1 contract: {exc}", pytrace=False
        )
    storage.create_branch_head(branch_head)
    created_ids.append(branch_head.id)

    try:
        scene_origin = scene_origin_cls(
            id=scene_origin_id,
            root_id=root_id,
            title="Scene 1",
            initial_commit_id=commit_id,
            sequence_index=1,
        )
    except TypeError as exc:
        pytest.fail(
            f"SceneOrigin model fields mismatch Phase1 contract: {exc}", pytrace=False
        )
    storage.create_scene_origin(scene_origin)
    created_ids.append(scene_origin_id)

    try:
        scene_version = scene_version_cls(
            id=scene_version_id,
            scene_origin_id=scene_origin_id,
            commit_id=commit_id,
            pov_character_id="character-1",
            status="draft",
            expected_outcome="expected",
            conflict_type="internal",
            actual_outcome="actual",
            summary="summary",
            rendered_content="content",
            logic_exception=False,
            logic_exception_reason=None,
            dirty=False,
        )
    except TypeError as exc:
        pytest.fail(
            f"SceneVersion model fields mismatch Phase1 contract: {exc}", pytrace=False
        )
    storage.create_scene_version(scene_version)
    created_ids.append(scene_version_id)

    try:
        entity = entity_cls(
            id=entity_id,
            root_id=root_id,
            branch_id="main",
            entity_type="Character",
            semantic_states={"hp": "100%"},
            arc_status="active",
        )
    except TypeError as exc:
        pytest.fail(f"Entity model fields mismatch Phase1 contract: {exc}", pytrace=False)
    storage.create_entity(entity)
    created_ids.append(entity_id)

    try:
        snapshot = world_snapshot_cls(
            id=snapshot_id,
            scene_version_id=scene_version_id,
            branch_id="main",
            scene_seq=1,
            entity_states={"entity": {"hp": "100%"}},
        )
    except TypeError as exc:
        pytest.fail(
            f"WorldSnapshot model fields mismatch Phase1 contract: {exc}",
            pytrace=False,
        )
    storage.create_world_snapshot(snapshot)
    created_ids.append(snapshot_id)

    branch.parent_branch_id = "parent-branch"
    storage.update_branch(branch)
    assert storage.get_branch(branch_id).parent_branch_id == "parent-branch"

    commit.message = "updated"
    storage.update_commit(commit)
    assert storage.get_commit(commit_id).message == "updated"

    branch_head.version = 2
    storage.update_branch_head(branch_head)
    assert storage.get_branch_head(branch_head.id).version == 2

    scene_origin.title = "Scene 1 updated"
    storage.update_scene_origin(scene_origin)
    assert storage.get_scene_origin(scene_origin_id).title == "Scene 1 updated"

    scene_version.summary = "summary updated"
    storage.update_scene_version(scene_version)
    assert storage.get_scene_version(scene_version_id).summary == "summary updated"

    entity.arc_status = "resolved"
    storage.update_entity(entity)
    assert storage.get_entity(entity_id).arc_status == "resolved"

    snapshot.scene_seq = 2
    storage.update_world_snapshot(snapshot)
    assert storage.get_world_snapshot(snapshot_id).scene_seq == 2

    storage.delete_world_snapshot(snapshot_id)
    assert storage.get_world_snapshot(snapshot_id) is None
    storage.delete_entity(entity_id)
    assert storage.get_entity(entity_id) is None
    storage.delete_scene_version(scene_version_id)
    assert storage.get_scene_version(scene_version_id) is None
    storage.delete_scene_origin(scene_origin_id)
    assert storage.get_scene_origin(scene_origin_id) is None
    storage.delete_branch_head(branch_head.id)
    assert storage.get_branch_head(branch_head.id) is None
    storage.delete_commit(commit_id)
    assert storage.get_commit(commit_id) is None
    storage.delete_branch(branch_id)
    assert storage.get_branch(branch_id) is None
    storage.delete_root(root_id)
    assert storage.get_root(root_id) is None

    storage.db.execute(
        "MATCH (n) WHERE n.id IN $ids DETACH DELETE n;",
        {"ids": created_ids},
    )


def test_memgraph_storage_phase1_relationship_crud():
    storage = _create_storage()
    _assert_memgraph_connection(storage)

    entity_a_id = f"entity-{uuid4()}"
    entity_b_id = f"entity-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"
    snapshot_id = f"snapshot-{uuid4()}"

    storage.db.execute(
        "CREATE (a:Entity {id: $entity_a}) "
        "CREATE (b:Entity {id: $entity_b}) "
        "CREATE (sv:SceneVersion {id: $scene_version}) "
        "CREATE (ws:WorldSnapshot {id: $snapshot});",
        {
            "entity_a": entity_a_id,
            "entity_b": entity_b_id,
            "scene_version": scene_version_id,
            "snapshot": snapshot_id,
        },
    )

    storage.db.execute(
        "MATCH (a:Entity {id: $entity_a}), (b:Entity {id: $entity_b}) "
        "CREATE (a)-[:TemporalRelation {branch_id: $branch_id, relation_type: $type, "
        "tension: $tension, start_scene_seq: $start_seq, end_scene_seq: $end_seq}]->(b);",
        {
            "entity_a": entity_a_id,
            "entity_b": entity_b_id,
            "branch_id": "main",
            "type": "HATES",
            "tension": 10,
            "start_seq": 1,
            "end_seq": 3,
        },
    )

    result = next(
        storage.db.execute_and_fetch(
            "MATCH (a:Entity {id: $entity_a})-[r:TemporalRelation]->(b:Entity {id: $entity_b}) "
            "RETURN r.tension AS tension, r.branch_id AS branch_id;",
            {"entity_a": entity_a_id, "entity_b": entity_b_id},
        ),
        None,
    )
    assert result is not None
    assert result["tension"] == 10
    assert result["branch_id"] == "main"

    storage.db.execute(
        "MATCH (a:Entity {id: $entity_a})-[r:TemporalRelation]->(b:Entity {id: $entity_b}) "
        "SET r.tension = $tension;",
        {"entity_a": entity_a_id, "entity_b": entity_b_id, "tension": 42},
    )
    updated = next(
        storage.db.execute_and_fetch(
            "MATCH (a:Entity {id: $entity_a})-[r:TemporalRelation]->(b:Entity {id: $entity_b}) "
            "RETURN r.tension AS tension;",
            {"entity_a": entity_a_id, "entity_b": entity_b_id},
        ),
        None,
    )
    assert updated is not None
    assert updated["tension"] == 42

    storage.db.execute(
        "MATCH (a:Entity {id: $entity_a})-[r:TemporalRelation]->(b:Entity {id: $entity_b}) DELETE r;",
        {"entity_a": entity_a_id, "entity_b": entity_b_id},
    )

    storage.db.execute(
        "MATCH (sv:SceneVersion {id: $scene_version}), (ws:WorldSnapshot {id: $snapshot}) "
        "CREATE (sv)-[:ESTABLISHES_STATE]->(ws);",
        {"scene_version": scene_version_id, "snapshot": snapshot_id},
    )
    bridge = next(
        storage.db.execute_and_fetch(
            "MATCH (sv:SceneVersion {id: $scene_version})-[r:ESTABLISHES_STATE]->(ws:WorldSnapshot {id: $snapshot}) "
            "RETURN r;",
            {"scene_version": scene_version_id, "snapshot": snapshot_id},
        ),
        None,
    )
    assert bridge is not None

    storage.db.execute(
        "MATCH (sv:SceneVersion {id: $scene_version})-[r:ESTABLISHES_STATE]->(ws:WorldSnapshot {id: $snapshot}) "
        "DELETE r;",
        {"scene_version": scene_version_id, "snapshot": snapshot_id},
    )

    storage.db.execute(
        "MATCH (n) WHERE n.id IN $ids DETACH DELETE n;",
        {"ids": [entity_a_id, entity_b_id, scene_version_id, snapshot_id]},
    )



def _index_by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items}


def test_memgraph_storage_create_branch_from_root_id(memgraph_storage):
    default_branch_id = _get_default_branch_id()
    root_id = f"root-{uuid4()}"
    commit_id = f"{root_id}:{default_branch_id}:{uuid4()}"
    _seed_root_with_default_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=default_branch_id,
        commit_id=commit_id,
    )

    created = memgraph_storage.create_branch(root_id=root_id, branch_id="feature")
    assert created.branch_id == "feature"
    assert created.root_id == root_id

    loaded = memgraph_storage.get_branch(created.id)
    assert loaded is not None
    assert loaded.branch_id == "feature"

    head_id = f"{root_id}:feature:head"
    head = memgraph_storage.get_branch_head(head_id)
    assert head is not None
    assert head.head_commit_id == commit_id
    assert head.version == 1


def test_memgraph_storage_create_entity_from_params(memgraph_storage):
    default_branch_id = _get_default_branch_id()
    root_id = f"root-{uuid4()}"
    commit_id = f"{root_id}:{default_branch_id}:{uuid4()}"
    _seed_root_with_default_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=default_branch_id,
        commit_id=commit_id,
    )

    entity_id = memgraph_storage.create_entity(
        root_id=root_id,
        branch_id=default_branch_id,
        name="Alice",
        entity_type="Character",
        tags=["hero"],
        arc_status="active",
        semantic_states={"hp": "100%"},
    )
    assert isinstance(entity_id, str)
    entity = memgraph_storage.get_entity(entity_id)
    assert entity is not None
    assert entity.name == "Alice"
    assert entity.entity_type == "Character"
    assert entity.tags == ["hero"]
    assert entity.arc_status == "active"
    assert entity.semantic_states == {"hp": "100%"}


def test_memgraph_storage_create_entity_requires_arc_status(memgraph_storage):
    default_branch_id = _get_default_branch_id()
    with pytest.raises(ValueError, match="arc_status is required"):
        memgraph_storage.create_entity(
            root_id="root-missing",
            branch_id=default_branch_id,
            name="Alice",
            entity_type="Character",
            tags=[],
            arc_status=None,
            semantic_states={},
        )


def test_memgraph_storage_migration_insert_delete_and_snapshot(memgraph_storage):
    node_a_id = f"node-{uuid4()}"
    node_b_id = f"node-{uuid4()}"
    edge_id = f"edge-{uuid4()}"

    memgraph_storage.insert_nodes(
        [
            {
                "id": node_a_id,
                "label": "Root",
                "properties": {
                    "logline": "seed",
                    "theme": "seed",
                    "ending": "seed",
                },
            },
            {
                "id": node_b_id,
                "label": "Entity",
                "properties": {
                    "root_id": node_a_id,
                    "branch_id": "main",
                    "entity_type": "Character",
                    "semantic_states": {"hp": "100%"},
                    "arc_status": "active",
                    "name": "Alice",
                },
            },
        ]
    )

    memgraph_storage.insert_edges(
        [
            {
                "id": edge_id,
                "type": "RELATES_TO",
                "from_id": node_a_id,
                "to_id": node_b_id,
                "properties": {"weight": 1},
            }
        ]
    )

    snapshot = memgraph_storage.snapshot()
    node_index = _index_by_id(snapshot["nodes"])
    edge_index = _index_by_id(snapshot["edges"])
    assert node_index[node_a_id]["label"] == "Root"
    assert node_index[node_a_id]["properties"]["logline"] == "seed"
    assert node_index[node_a_id]["properties"]["ending"] == "seed"
    assert node_index[node_b_id]["properties"]["name"] == "Alice"
    assert node_index[node_b_id]["properties"]["root_id"] == node_a_id
    assert node_index[node_b_id]["properties"]["branch_id"] == "main"
    assert edge_index[edge_id]["type"] == "RELATES_TO"
    assert edge_index[edge_id]["from_id"] == node_a_id
    assert edge_index[edge_id]["to_id"] == node_b_id
    assert edge_index[edge_id]["properties"]["weight"] == 1

    memgraph_storage.delete_edges([edge_id])
    memgraph_storage.delete_nodes([node_a_id, node_b_id])

    empty_snapshot = memgraph_storage.snapshot()
    assert empty_snapshot["nodes"] == []
    assert empty_snapshot["edges"] == []


@pytest.mark.parametrize(
    ("nodes", "message"),
    [
        ([{"label": "Root", "properties": {}}], "node id is required"),
        ([{"id": "node-1", "properties": {}}], "node label is required"),
    ],
)
def test_memgraph_storage_insert_nodes_requires_fields(memgraph_storage, nodes, message):
    with pytest.raises(ValueError, match=message):
        memgraph_storage.insert_nodes(nodes)


@pytest.mark.parametrize(
    ("edges", "message"),
    [
        ([{"type": "REL", "from_id": "a", "to_id": "b"}], "edge id is required"),
        ([{"id": "edge-1", "from_id": "a", "to_id": "b"}], "edge type is required"),
        (
            [{"id": "edge-1", "type": "REL", "from_id": "a"}],
            "edge endpoints are required",
        ),
    ],
)
def test_memgraph_storage_insert_edges_requires_fields(memgraph_storage, edges, message):
    with pytest.raises(ValueError, match=message):
        memgraph_storage.insert_edges(edges)



def test_memgraph_storage_graph_port_flow(memgraph_storage):
    default_branch_id = _get_default_branch_id()
    root_id = f"root-{uuid4()}"
    seed_commit_id = f"{root_id}:{default_branch_id}:{uuid4()}"
    _seed_root_with_default_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=default_branch_id,
        commit_id=seed_commit_id,
    )

    scene_content = {
        "expected_outcome": "safe",
        "conflict_type": "internal",
        "actual_outcome": "safe",
        "summary": "seed summary",
        "rendered_content": "seed render",
        "pov_character_id": "pov-1",
        "status": "draft",
    }
    created_scene = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=default_branch_id,
        title="Scene 1",
        parent_act_id="act-1",
        content=scene_content,
    )
    scene_origin_id = created_scene["scene_origin_id"]
    scene_commit_id = created_scene["commit_id"]

    entity_id = memgraph_storage.create_entity(
        root_id=root_id,
        branch_id=default_branch_id,
        name="Alice",
        entity_type="Character",
        tags=["hero"],
        arc_status="active",
        semantic_states={"hp": "100%"},
    )
    location_id = memgraph_storage.create_entity(
        root_id=root_id,
        branch_id=default_branch_id,
        name="Town",
        entity_type="Location",
        tags=[],
        arc_status="stable",
        semantic_states={"kind": "place"},
    )

    memgraph_storage.upsert_entity_relation(
        root_id=root_id,
        branch_id=default_branch_id,
        from_entity_id=entity_id,
        to_entity_id=location_id,
        relation_type="AT",
        tension=5,
    )

    created_scene_2 = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=default_branch_id,
        title="Scene 2",
        parent_act_id="act-1",
        content={
            "expected_outcome": "escape",
            "conflict_type": "external",
            "actual_outcome": "escape",
            "summary": "second summary",
            "rendered_content": "second render",
            "pov_character_id": "pov-1",
            "status": "draft",
        },
    )
    scene_origin_id_2 = created_scene_2["scene_origin_id"]

    branches = memgraph_storage.list_branches(root_id=root_id)
    assert branches == [default_branch_id]
    memgraph_storage.require_branch(root_id=root_id, branch_id=default_branch_id)
    memgraph_storage.require_root(root_id=root_id, branch_id=default_branch_id)

    snapshot = memgraph_storage.get_root_snapshot(root_id=root_id, branch_id=default_branch_id)
    assert snapshot["root_id"] == root_id
    assert snapshot["branch_id"] == default_branch_id
    assert snapshot["characters"] == [
        {
            "entity_id": entity_id,
            "name": "Alice",
            "ambition": "",
            "conflict": "",
            "epiphany": "",
            "voice_dna": "",
        }
    ]
    assert snapshot["relations"] == [
        {
            "from_entity_id": entity_id,
            "to_entity_id": location_id,
            "relation_type": "AT",
            "tension": 5,
        }
    ]

    context = memgraph_storage.get_scene_context(
        scene_id=scene_origin_id,
        branch_id=default_branch_id,
    )
    assert context["root_id"] == root_id
    assert context["next_scene_id"] == scene_origin_id_2
    assert entity_id in context["semantic_states"]

    memgraph_storage.mark_scene_dirty(scene_id=scene_origin_id, branch_id=default_branch_id)
    dirty = memgraph_storage.list_dirty_scenes(root_id=root_id, branch_id=default_branch_id)
    assert scene_origin_id in dirty

    future_dirty = memgraph_storage.mark_future_scenes_dirty(
        root_id=root_id,
        branch_id=default_branch_id,
        scene_id=scene_origin_id,
    )
    assert scene_origin_id_2 in future_dirty

    assert memgraph_storage.apply_local_scene_fix(
        root_id=root_id,
        branch_id=default_branch_id,
        scene_id=scene_origin_id,
    ) == [scene_origin_id]

    states = memgraph_storage.get_entity_semantic_states(
        root_id=root_id,
        branch_id=default_branch_id,
        entity_id=entity_id,
    )
    assert states == {"hp": "100%"}
    updated = memgraph_storage.apply_semantic_states_patch(
        root_id=root_id,
        branch_id=default_branch_id,
        entity_id=entity_id,
        patch={"mood": "calm"},
    )
    assert updated["mood"] == "calm"

    world_state = memgraph_storage.build_logic_check_world_state(
        root_id=root_id,
        branch_id=default_branch_id,
        scene_id=scene_origin_id,
    )
    assert world_state[entity_id]["AT"] == location_id

    commit_result = memgraph_storage.commit_scene(
        root_id=root_id,
        branch_id=default_branch_id,
        scene_origin_id=scene_origin_id,
        content={
            "expected_outcome": "escape",
            "conflict_type": "external",
            "actual_outcome": "escape",
            "summary": "updated summary",
            "rendered_content": "updated render",
            "pov_character_id": "pov-1",
            "status": "draft",
        },
        message="update",
    )
    commit_id = commit_result["commit_id"]

    history = memgraph_storage.get_branch_history(
        root_id=root_id,
        branch_id=default_branch_id,
    )
    assert any(item["id"] == commit_id for item in history)

    diff = memgraph_storage.diff_scene_versions(
        scene_origin_id=scene_origin_id,
        from_commit_id=scene_commit_id,
        to_commit_id=commit_id,
    )
    assert "summary" in diff

    memgraph_storage.save_scene_render(
        scene_id=scene_origin_id,
        branch_id=default_branch_id,
        content="rendered",
    )
    memgraph_storage.complete_scene(
        scene_id=scene_origin_id,
        branch_id=default_branch_id,
        actual_outcome="done",
        summary="summary",
    )
    record = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id}) "
            "RETURN sv.rendered_content AS rendered, sv.status AS status, sv.summary AS summary;",
            {"scene_origin_id": scene_origin_id},
        ),
        None,
    )
    assert record is not None
    assert record["rendered"] == "rendered"
    assert record["status"] == "committed"
    assert record["summary"] == "summary"

    memgraph_storage.mark_scene_logic_exception(
        root_id=root_id,
        branch_id=default_branch_id,
        scene_id=scene_origin_id,
        reason="oops",
    )
    assert (
        memgraph_storage.is_scene_logic_exception(
            root_id=root_id,
            branch_id=default_branch_id,
            scene_id=scene_origin_id,
        )
        is True
    )

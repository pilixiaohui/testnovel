import importlib
import importlib.util
from concurrent.futures import ThreadPoolExecutor
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
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_world_state_service_class():
    module = _import_module("app.services.world_state_service")
    if not hasattr(module, "WorldStateService"):
        pytest.fail("WorldStateService class is missing", pytrace=False)
    return module.WorldStateService


def _get_temporal_edge_manager_class():
    module = _import_module("app.storage.temporal_edge")
    if not hasattr(module, "TemporalEdgeManager"):
        pytest.fail("TemporalEdgeManager class is missing", pytrace=False)
    return module.TemporalEdgeManager


def _get_schema_model(name: str):
    module = _import_module("app.storage.schema")
    if not hasattr(module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    return getattr(module, name)


def _create_entity(storage, *, entity_id: str, root_id: str, branch_id: str, entity_type: str):
    entity_cls = _get_schema_model("Entity")
    entity = entity_cls(
        id=entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type=entity_type,
        semantic_states={},
        arc_status="active",
    )
    storage.create_entity(entity)


def _require_method(obj, name: str):
    if not hasattr(obj, name):
        pytest.fail(f"{obj.__class__.__name__}.{name} is missing", pytrace=False)
    method = getattr(obj, name)
    if not callable(method):
        pytest.fail(f"{obj.__class__.__name__}.{name} must be callable", pytrace=False)
    return method


def test_world_state_service_write_and_restore(memgraph_storage):
    service_cls = _get_world_state_service_class()
    service = service_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    home_id = f"entity-{uuid4()}"
    hospital_id = f"entity-{uuid4()}"
    park_id = f"entity-{uuid4()}"
    school_id = f"entity-{uuid4()}"

    _create_entity(
        memgraph_storage,
        entity_id=from_entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
    )
    _create_entity(
        memgraph_storage,
        entity_id=home_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )
    _create_entity(
        memgraph_storage,
        entity_id=hospital_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )
    _create_entity(
        memgraph_storage,
        entity_id=park_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )
    _create_entity(
        memgraph_storage,
        entity_id=school_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )

    upsert = _require_method(service, "upsert_relation")
    build_world_state = _require_method(service, "build_world_state")

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )
    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=hospital_id,
        relation_type="AT",
        tension=20,
        scene_seq=5,
        branch_id=branch_id,
    )

    world_state_3 = build_world_state(branch_id=branch_id, scene_seq=3)
    assert world_state_3[from_entity_id]["AT"] == home_id

    world_state_5 = build_world_state(branch_id=branch_id, scene_seq=5)
    assert world_state_5[from_entity_id]["AT"] == hospital_id

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=park_id,
        relation_type="AT",
        tension=30,
        scene_seq=10,
        branch_id=branch_id,
    )
    snapshot = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (s:WorldSnapshot {branch_id: $branch_id, scene_seq: $scene_seq}) "
            "RETURN s.id AS snapshot_id;",
            {"branch_id": branch_id, "scene_seq": 10},
        ),
        None,
    )
    assert snapshot is not None

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=school_id,
        relation_type="AT",
        tension=40,
        scene_seq=12,
        branch_id=branch_id,
    )
    world_state_12 = build_world_state(branch_id=branch_id, scene_seq=12)
    assert world_state_12[from_entity_id]["AT"] == school_id


def test_world_state_service_end_to_end_with_snapshot(memgraph_storage):
    service_cls = _get_world_state_service_class()
    temporal_cls = _get_temporal_edge_manager_class()
    service = service_cls(memgraph_storage.db)
    temporal = temporal_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    home_id = f"entity-{uuid4()}"
    hospital_id = f"entity-{uuid4()}"

    _create_entity(
        memgraph_storage,
        entity_id=from_entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
    )
    _create_entity(
        memgraph_storage,
        entity_id=home_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )
    _create_entity(
        memgraph_storage,
        entity_id=hospital_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )

    upsert = _require_method(service, "upsert_relation")
    build_world_state = _require_method(service, "build_world_state")
    query_relations = _require_method(temporal, "query_relations_at_scene")

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )
    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=hospital_id,
        relation_type="AT",
        tension=20,
        scene_seq=10,
        branch_id=branch_id,
    )

    relations = query_relations(
        from_entity_id=from_entity_id,
        branch_id=branch_id,
        scene_seq=10,
    )
    assert len(relations) == 1
    assert relations[0]["to_entity_id"] == hospital_id

    snapshot_record = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (s:WorldSnapshot {branch_id: $branch_id, scene_seq: $scene_seq}) "
            "RETURN s.entity_states AS entity_states;",
            {"branch_id": branch_id, "scene_seq": 10},
        ),
        None,
    )
    assert snapshot_record is not None
    snapshot_state = snapshot_record["entity_states"]
    assert snapshot_state[from_entity_id]["AT"] == hospital_id

    world_state = build_world_state(branch_id=branch_id, scene_seq=10)
    assert world_state[from_entity_id]["AT"] == hospital_id


def test_world_state_service_concurrent_writes(memgraph_storage):
    service_cls = _get_world_state_service_class()
    service = service_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    pairs = []
    for idx in range(5):
        from_entity_id = f"entity-{uuid4()}"
        to_entity_id = f"entity-{uuid4()}"
        _create_entity(
            memgraph_storage,
            entity_id=from_entity_id,
            root_id=root_id,
            branch_id=branch_id,
            entity_type="Character",
        )
        _create_entity(
            memgraph_storage,
            entity_id=to_entity_id,
            root_id=root_id,
            branch_id=branch_id,
            entity_type="Location",
        )
        pairs.append((from_entity_id, to_entity_id, idx + 1))

    def _write_relation(from_id: str, to_id: str, scene_seq: int) -> None:
        service.upsert_relation(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type="AT",
            tension=scene_seq * 10,
            scene_seq=scene_seq,
            branch_id=branch_id,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_write_relation, from_id, to_id, scene_seq)
            for from_id, to_id, scene_seq in pairs
        ]
        for future in futures:
            future.result()

    record = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH ()-[r:TemporalRelation {branch_id: $branch_id}]->() "
            "RETURN count(r) AS count;",
            {"branch_id": branch_id},
        ),
        None,
    )
    assert record is not None
    assert record["count"] == len(pairs)

    world_state = service.build_world_state(
        branch_id=branch_id,
        scene_seq=max(scene_seq for _, _, scene_seq in pairs),
    )
    for from_id, to_id, _ in pairs:
        assert world_state[from_id]["AT"] == to_id

def test_world_state_service_establishes_state_bridge(memgraph_storage, monkeypatch):
    module = _import_module("app.services.world_state_service")
    fixed_uuid = uuid4()
    monkeypatch.setattr(module, "uuid4", lambda: fixed_uuid)

    service_cls = _get_world_state_service_class()
    service = service_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    to_entity_id = f"entity-{uuid4()}"

    _create_entity(
        memgraph_storage,
        entity_id=from_entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
    )
    _create_entity(
        memgraph_storage,
        entity_id=to_entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )

    scene_version_id = str(fixed_uuid)
    memgraph_storage.db.execute(
        "CREATE (sv:SceneVersion {id: $id, scene_origin_id: $scene_origin_id, "
        "commit_id: $commit_id, pov_character_id: $pov_character_id, status: $status, "
        "expected_outcome: $expected_outcome, conflict_type: $conflict_type, "
        "actual_outcome: $actual_outcome});",
        {
            "id": scene_version_id,
            "scene_origin_id": f"scene-origin-{uuid4()}",
            "commit_id": f"commit-{uuid4()}",
            "pov_character_id": f"entity-{uuid4()}",
            "status": "draft",
            "expected_outcome": "stay_safe",
            "conflict_type": "internal",
            "actual_outcome": "stay_safe",
        },
    )

    service.upsert_relation(
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type="AT",
        tension=10,
        scene_seq=10,
        branch_id=branch_id,
    )

    snapshot_record = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (s:WorldSnapshot {scene_version_id: $scene_version_id}) "
            "RETURN s.id AS snapshot_id;",
            {"scene_version_id": scene_version_id},
        ),
        None,
    )
    assert snapshot_record is not None

    bridge_record = next(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (sv:SceneVersion {id: $scene_version_id})"
            "-[:ESTABLISHES_STATE]->"
            "(s:WorldSnapshot {scene_version_id: $scene_version_id}) "
            "RETURN s.id AS snapshot_id;",
            {"scene_version_id": scene_version_id},
        ),
        None,
    )
    assert bridge_record is not None

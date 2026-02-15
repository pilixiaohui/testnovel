import importlib
import importlib.util
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


def _get_snapshot_manager_class():
    module = _import_module("app.storage.snapshot")
    if not hasattr(module, "SnapshotManager"):
        pytest.fail("SnapshotManager class is missing", pytrace=False)
    return module.SnapshotManager


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


def test_snapshot_interval_rule(memgraph_storage):
    manager_cls = _get_snapshot_manager_class()
    manager = manager_cls(memgraph_storage.db)

    should_create = _require_method(manager, "should_create_snapshot")
    assert should_create(scene_seq=10) is True
    assert should_create(scene_seq=20) is True
    assert should_create(scene_seq=11) is False


def test_snapshot_creation_captures_current_state(memgraph_storage):
    snapshot_cls = _get_snapshot_manager_class()
    temporal_cls = _get_temporal_edge_manager_class()

    snapshot_manager = snapshot_cls(memgraph_storage.db)
    temporal_manager = temporal_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    home_id = f"entity-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"

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

    upsert = _require_method(temporal_manager, "upsert_relation")
    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )

    create_snapshot = _require_method(snapshot_manager, "create_snapshot_if_needed")
    snapshot = create_snapshot(
        scene_version_id=scene_version_id,
        branch_id=branch_id,
        scene_seq=10,
    )
    assert snapshot is not None
    assert snapshot.scene_version_id == scene_version_id
    assert snapshot.branch_id == branch_id
    assert snapshot.scene_seq == 10
    assert from_entity_id in snapshot.entity_states
    assert snapshot.entity_states[from_entity_id]["AT"] == home_id

def test_snapshot_query_prefers_latest_snapshot_before_target(memgraph_storage):
    snapshot_cls = _get_snapshot_manager_class()
    temporal_cls = _get_temporal_edge_manager_class()

    snapshot_manager = snapshot_cls(memgraph_storage.db)
    temporal_manager = temporal_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    home_id = f"entity-{uuid4()}"
    hospital_id = f"entity-{uuid4()}"
    scene_version_id_10 = f"scene-version-{uuid4()}"
    scene_version_id_20 = f"scene-version-{uuid4()}"

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

    upsert = _require_method(temporal_manager, "upsert_relation")
    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )

    create_snapshot = _require_method(snapshot_manager, "create_snapshot_if_needed")
    snapshot_10 = create_snapshot(
        scene_version_id=scene_version_id_10,
        branch_id=branch_id,
        scene_seq=10,
    )
    assert snapshot_10 is not None

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=hospital_id,
        relation_type="AT",
        tension=20,
        scene_seq=20,
        branch_id=branch_id,
    )
    snapshot_20 = create_snapshot(
        scene_version_id=scene_version_id_20,
        branch_id=branch_id,
        scene_seq=20,
    )
    assert snapshot_20 is not None

    build_state = _require_method(memgraph_storage, "_build_scene_context_state")
    world_state, _ = build_state(
        root_id=root_id,
        branch_id=branch_id,
        scene_seq=12,
    )
    assert world_state[from_entity_id]["AT"] == home_id


def test_snapshot_incremental_replay_applies_changes(memgraph_storage):
    snapshot_cls = _get_snapshot_manager_class()
    temporal_cls = _get_temporal_edge_manager_class()

    snapshot_manager = snapshot_cls(memgraph_storage.db)
    temporal_manager = temporal_cls(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    from_entity_id = f"entity-{uuid4()}"
    home_id = f"entity-{uuid4()}"
    school_id = f"entity-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"

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
        entity_id=school_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Location",
    )

    upsert = _require_method(temporal_manager, "upsert_relation")
    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )

    create_snapshot = _require_method(snapshot_manager, "create_snapshot_if_needed")
    snapshot = create_snapshot(
        scene_version_id=scene_version_id,
        branch_id=branch_id,
        scene_seq=10,
    )
    assert snapshot is not None

    upsert(
        from_entity_id=from_entity_id,
        to_entity_id=school_id,
        relation_type="AT",
        tension=30,
        scene_seq=12,
        branch_id=branch_id,
    )

    build_state = _require_method(memgraph_storage, "_build_scene_context_state")
    world_state, relations = build_state(
        root_id=root_id,
        branch_id=branch_id,
        scene_seq=12,
    )
    assert world_state[from_entity_id]["AT"] == school_id
    assert any(
        rel["from_entity_id"] == from_entity_id
        and rel["relation_type"] == "AT"
        and rel["to_entity_id"] == school_id
        for rel in relations
    )

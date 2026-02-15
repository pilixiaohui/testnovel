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


def _get_schema_model(name: str):
    module = _import_module("app.storage.schema")
    if not hasattr(module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    return getattr(module, name)


def _get_temporal_edge_manager_class():
    module = _import_module("app.storage.temporal_edge")
    if not hasattr(module, "TemporalEdgeManager"):
        pytest.fail("TemporalEdgeManager class is missing", pytrace=False)
    return module.TemporalEdgeManager


def _get_snapshot_manager_class():
    module = _import_module("app.storage.snapshot")
    if not hasattr(module, "SnapshotManager"):
        pytest.fail("SnapshotManager class is missing", pytrace=False)
    return module.SnapshotManager


def _count_nodes(storage, label: str) -> int:
    record = next(
        storage.db.execute_and_fetch(
            f"MATCH (n:{label}) RETURN count(n) AS count;",
        ),
        None,
    )
    return 0 if record is None else record["count"]


def _count_edges(storage, rel_type: str) -> int:
    record = next(
        storage.db.execute_and_fetch(
            f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS count;",
        ),
        None,
    )
    return 0 if record is None else record["count"]


def _create_root(storage, *, root_id: str):
    root_cls = _get_schema_model("Root")
    root = root_cls(
        id=root_id,
        logline="Test logline",
        theme="Test theme",
        ending="Test ending",
    )
    storage.create_root(root)


def _create_branch(storage, *, branch_node_id: str, root_id: str, branch_id: str):
    branch_cls = _get_schema_model("Branch")
    branch = branch_cls(
        id=branch_node_id,
        root_id=root_id,
        branch_id=branch_id,
    )
    storage.create_branch(branch)


def _create_commit(storage, *, commit_id: str, root_id: str):
    commit_cls = _get_schema_model("Commit")
    commit = commit_cls(
        id=commit_id,
        created_at="2024-01-01T00:00:00Z",
        root_id=root_id,
    )
    storage.create_commit(commit)


def _create_scene_origin(
    storage,
    *,
    scene_origin_id: str,
    root_id: str,
    title: str,
    initial_commit_id: str,
    sequence_index: int,
):
    scene_origin_cls = _get_schema_model("SceneOrigin")
    scene_origin = scene_origin_cls(
        id=scene_origin_id,
        root_id=root_id,
        title=title,
        initial_commit_id=initial_commit_id,
        sequence_index=sequence_index,
    )
    storage.create_scene_origin(scene_origin)


def _create_scene_version(
    storage,
    *,
    scene_version_id: str,
    scene_origin_id: str,
    commit_id: str,
    pov_character_id: str,
):
    scene_version_cls = _get_schema_model("SceneVersion")
    scene_version = scene_version_cls(
        id=scene_version_id,
        scene_origin_id=scene_origin_id,
        commit_id=commit_id,
        pov_character_id=pov_character_id,
        status="draft",
        expected_outcome="stay",
        conflict_type="internal",
        actual_outcome="stay",
        logic_exception=False,
        dirty=False,
    )
    storage.create_scene_version(scene_version)


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


def _reset_storage(storage) -> None:
    storage.db.execute("MATCH (n) DETACH DELETE n;")


def test_structure_subgraph_does_not_touch_narrative(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_node_id = f"branch-{uuid4()}"
    branch_id = "main"
    commit_id = f"commit-{uuid4()}"
    scene_origin_id = f"scene-origin-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"

    _create_root(memgraph_storage, root_id=root_id)
    _create_branch(
        memgraph_storage,
        branch_node_id=branch_node_id,
        root_id=root_id,
        branch_id=branch_id,
    )
    _create_commit(memgraph_storage, commit_id=commit_id, root_id=root_id)
    _create_scene_origin(
        memgraph_storage,
        scene_origin_id=scene_origin_id,
        root_id=root_id,
        title="Scene 1",
        initial_commit_id=commit_id,
        sequence_index=1,
    )
    _create_scene_version(
        memgraph_storage,
        scene_version_id=scene_version_id,
        scene_origin_id=scene_origin_id,
        commit_id=commit_id,
        pov_character_id="pov-1",
    )

    assert memgraph_storage.get_root(root_id) is not None
    assert memgraph_storage.get_branch(branch_node_id) is not None
    assert memgraph_storage.get_commit(commit_id) is not None
    assert memgraph_storage.get_scene_origin(scene_origin_id) is not None
    assert memgraph_storage.get_scene_version(scene_version_id) is not None

    assert _count_nodes(memgraph_storage, "Entity") == 0
    assert _count_edges(memgraph_storage, "TemporalRelation") == 0
    assert _count_nodes(memgraph_storage, "WorldSnapshot") == 0


def test_narrative_subgraph_does_not_touch_structure(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_node_id = f"branch-{uuid4()}"
    branch_id = "main"
    commit_id = f"commit-{uuid4()}"
    scene_origin_id = f"scene-origin-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"

    _create_root(memgraph_storage, root_id=root_id)
    _create_branch(
        memgraph_storage,
        branch_node_id=branch_node_id,
        root_id=root_id,
        branch_id=branch_id,
    )
    _create_commit(memgraph_storage, commit_id=commit_id, root_id=root_id)
    _create_scene_origin(
        memgraph_storage,
        scene_origin_id=scene_origin_id,
        root_id=root_id,
        title="Scene 1",
        initial_commit_id=commit_id,
        sequence_index=1,
    )
    _create_scene_version(
        memgraph_storage,
        scene_version_id=scene_version_id,
        scene_origin_id=scene_origin_id,
        commit_id=commit_id,
        pov_character_id="pov-1",
    )

    structural_counts = {
        "Root": _count_nodes(memgraph_storage, "Root"),
        "Branch": _count_nodes(memgraph_storage, "Branch"),
        "Commit": _count_nodes(memgraph_storage, "Commit"),
        "SceneOrigin": _count_nodes(memgraph_storage, "SceneOrigin"),
        "SceneVersion": _count_nodes(memgraph_storage, "SceneVersion"),
    }

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

    temporal_cls = _get_temporal_edge_manager_class()
    temporal_manager = temporal_cls(memgraph_storage.db)
    temporal_manager.upsert_relation(
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )

    snapshot_cls = _get_snapshot_manager_class()
    snapshot_manager = snapshot_cls(memgraph_storage.db)
    snapshot = snapshot_manager.create_snapshot_if_needed(
        scene_version_id=scene_version_id,
        branch_id=branch_id,
        scene_seq=10,
    )
    assert snapshot is not None

    assert _count_nodes(memgraph_storage, "Entity") == 2
    assert _count_edges(memgraph_storage, "TemporalRelation") == 1
    assert _count_nodes(memgraph_storage, "WorldSnapshot") == 1

    assert _count_nodes(memgraph_storage, "Root") == structural_counts["Root"]
    assert _count_nodes(memgraph_storage, "Branch") == structural_counts["Branch"]
    assert _count_nodes(memgraph_storage, "Commit") == structural_counts["Commit"]
    assert _count_nodes(memgraph_storage, "SceneOrigin") == structural_counts["SceneOrigin"]
    assert _count_nodes(memgraph_storage, "SceneVersion") == structural_counts["SceneVersion"]


def test_structure_edges_sweep_for_coverage(memgraph_storage):
    from tests.integration import test_structure_edges as structure_edges

    cases = [
        structure_edges.test_structure_edges_on_scene_origin_flow,
        structure_edges.test_structure_edges_branch_head_moves_and_commit_chain,
        structure_edges.test_structure_edges_delete_scene_origin_updates_head_and_cleans_versions,
        structure_edges.test_structure_edges_crud_roundtrip,
        structure_edges.test_structure_edges_branch_management_and_history,
        structure_edges.test_structure_edges_scene_updates_and_flags,
        structure_edges.test_structure_edges_entities_relations_and_context,
        structure_edges.test_structure_edges_save_snowflake,
        structure_edges.test_structure_edges_bulk_insert_and_snapshot,
    ]
    for case in cases:
        _reset_storage(memgraph_storage)
        case(memgraph_storage)


def test_memgraph_storage_getters_and_snapshot_roundtrip(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = "main"
    branch_node_id = f"{root_id}:{branch_id}"
    commit_id = f"commit-{uuid4()}"
    scene_origin_id = f"scene-origin-{uuid4()}"
    scene_version_id = f"scene-version-{uuid4()}"
    entity_id = f"entity-{uuid4()}"

    _create_root(memgraph_storage, root_id=root_id)
    _create_branch(
        memgraph_storage,
        branch_node_id=branch_node_id,
        root_id=root_id,
        branch_id=branch_id,
    )
    _create_commit(memgraph_storage, commit_id=commit_id, root_id=root_id)
    _create_scene_origin(
        memgraph_storage,
        scene_origin_id=scene_origin_id,
        root_id=root_id,
        title="Scene 1",
        initial_commit_id=commit_id,
        sequence_index=1,
    )
    _create_scene_version(
        memgraph_storage,
        scene_version_id=scene_version_id,
        scene_origin_id=scene_origin_id,
        commit_id=commit_id,
        pov_character_id="pov-1",
    )
    _create_entity(
        memgraph_storage,
        entity_id=entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
    )

    assert memgraph_storage.get_branch(branch_node_id) is not None
    assert memgraph_storage.get_entity(entity_id) is not None

    snapshot_cls = _get_schema_model("WorldSnapshot")
    snapshot = snapshot_cls(
        id=f"snapshot-{uuid4()}",
        scene_version_id=scene_version_id,
        branch_id=branch_id,
        scene_seq=1,
        entity_states={"entity": {"state": "ok"}},
        relations=[],
    )
    memgraph_storage.create_world_snapshot(snapshot)

    loaded = memgraph_storage.get_world_snapshot(snapshot.id)
    assert loaded is not None
    assert loaded.scene_seq == 1

    snapshot.scene_seq = 2
    memgraph_storage.update_world_snapshot(snapshot)
    assert memgraph_storage.get_world_snapshot(snapshot.id).scene_seq == 2

    memgraph_storage.delete_world_snapshot(snapshot.id)
    assert memgraph_storage.get_world_snapshot(snapshot.id) is None

    memgraph_storage.delete_entity(entity_id)
    assert memgraph_storage.get_entity(entity_id) is None

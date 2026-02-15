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


def test_temporal_edge_invalidation_preserves_history(memgraph_storage):
    manager_cls = _get_temporal_edge_manager_class()
    manager = manager_cls(memgraph_storage.db)

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

    upsert = _require_method(manager, "upsert_relation")
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

    records = list(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (a:Entity {id: $from_id})-"
            "[r:TemporalRelation {branch_id: $branch_id, relation_type: $relation_type}]->"
            "(b:Entity) "
            "RETURN b.id AS to_id, r.start_scene_seq AS start_seq, r.end_scene_seq AS end_seq "
            "ORDER BY r.start_scene_seq ASC;",
            {
                "from_id": from_entity_id,
                "branch_id": branch_id,
                "relation_type": "AT",
            },
        )
    )

    assert len(records) == 2
    by_target = {record["to_id"]: record for record in records}
    assert by_target[home_id]["start_seq"] == 1
    assert by_target[home_id]["end_seq"] == 5
    assert by_target[hospital_id]["start_seq"] == 5
    assert by_target[hospital_id]["end_seq"] is None


def test_temporal_edge_time_travel_query(memgraph_storage):
    manager_cls = _get_temporal_edge_manager_class()
    manager = manager_cls(memgraph_storage.db)

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

    upsert = _require_method(manager, "upsert_relation")
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

    query = _require_method(manager, "query_relations_at_scene")
    at_scene_3 = query(
        from_entity_id=from_entity_id,
        branch_id=branch_id,
        scene_seq=3,
    )
    assert len(at_scene_3) == 1
    assert at_scene_3[0]["to_entity_id"] == home_id
    assert at_scene_3[0]["relation_type"] == "AT"

    at_scene_5 = query(
        from_entity_id=from_entity_id,
        branch_id=branch_id,
        scene_seq=5,
    )
    assert len(at_scene_5) == 1
    assert at_scene_5[0]["to_entity_id"] == hospital_id
    assert at_scene_5[0]["relation_type"] == "AT"


def test_temporal_edge_build_world_state_filters_root(memgraph_storage):
    manager_cls = _get_temporal_edge_manager_class()
    manager = manager_cls(memgraph_storage.db)

    root_a = f"root-{uuid4()}"
    root_b = f"root-{uuid4()}"
    branch_id = "main"
    from_a = f"entity-{uuid4()}"
    to_a = f"entity-{uuid4()}"
    from_b = f"entity-{uuid4()}"
    to_b = f"entity-{uuid4()}"

    _create_entity(
        memgraph_storage,
        entity_id=from_a,
        root_id=root_a,
        branch_id=branch_id,
        entity_type="Character",
    )
    _create_entity(
        memgraph_storage,
        entity_id=to_a,
        root_id=root_a,
        branch_id=branch_id,
        entity_type="Location",
    )
    _create_entity(
        memgraph_storage,
        entity_id=from_b,
        root_id=root_b,
        branch_id=branch_id,
        entity_type="Character",
    )
    _create_entity(
        memgraph_storage,
        entity_id=to_b,
        root_id=root_b,
        branch_id=branch_id,
        entity_type="Location",
    )

    manager.upsert_relation(
        from_entity_id=from_a,
        to_entity_id=to_a,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )
    manager.upsert_relation(
        from_entity_id=from_b,
        to_entity_id=to_b,
        relation_type="AT",
        tension=20,
        scene_seq=1,
        branch_id=branch_id,
    )

    world_state_root_a = manager.build_world_state(
        branch_id=branch_id,
        scene_seq=1,
        root_id=root_a,
    )
    assert world_state_root_a == {from_a: {"AT": to_a}}

    world_state_all = manager.build_world_state(branch_id=branch_id, scene_seq=1)
    assert world_state_all[from_a]["AT"] == to_a
    assert world_state_all[from_b]["AT"] == to_b


def test_temporal_edge_build_world_state_with_relations(memgraph_storage):
    manager_cls = _get_temporal_edge_manager_class()
    manager = manager_cls(memgraph_storage.db)

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

    manager.upsert_relation(
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type="AT",
        tension=33,
        scene_seq=2,
        branch_id=branch_id,
    )

    world_state, relations = manager.build_world_state_with_relations(
        branch_id=branch_id,
        scene_seq=2,
        root_id=root_id,
    )

    assert world_state == {from_entity_id: {"AT": to_entity_id}}
    assert relations == [
        {
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relation_type": "AT",
            "tension": 33,
        }
    ]


def test_temporal_edge_duplicate_active_relations_raise(memgraph_storage):
    manager_cls = _get_temporal_edge_manager_class()
    manager = manager_cls(memgraph_storage.db)

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

    manager.upsert_relation(
        from_entity_id=from_entity_id,
        to_entity_id=home_id,
        relation_type="AT",
        tension=10,
        scene_seq=1,
        branch_id=branch_id,
    )
    manager.upsert_relation(
        from_entity_id=from_entity_id,
        to_entity_id=hospital_id,
        relation_type="AT",
        tension=20,
        scene_seq=1,
        branch_id=branch_id,
    )

    with pytest.raises(ValueError, match="multiple active relations detected"):
        manager.build_world_state(branch_id=branch_id, scene_seq=1)

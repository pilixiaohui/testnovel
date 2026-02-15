from uuid import uuid4

from tests.integration import storage_test_helpers as helpers


def _seed_root(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = helpers.get_default_branch_id()
    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    helpers.seed_root_with_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        commit_id=commit_id,
    )
    return root_id, branch_id


def test_simulation_log_crud(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    created_scene = helpers.create_scene_origin(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
    )
    scene_version_id = created_scene["scene_version_id"]

    simulation_cls = helpers.get_schema_model("SimulationLog")
    simulation = simulation_cls(
        id=f"sim:{scene_version_id}:round:1",
        scene_version_id=scene_version_id,
        round_number=1,
        agent_actions="[]",
        dm_arbitration="{}",
        narrative_events="[]",
        sensory_seeds="[]",
        convergence_score=0.5,
        drama_score=0.6,
        info_gain=0.3,
    )

    memgraph_storage.create_simulation_log(simulation)
    loaded = memgraph_storage.get_simulation_log(simulation.id)
    assert loaded is not None
    assert loaded.info_gain == 0.3

    simulation.info_gain = 0.7
    memgraph_storage.update_simulation_log(simulation)
    updated = memgraph_storage.get_simulation_log(simulation.id)
    assert updated is not None
    assert updated.info_gain == 0.7

    memgraph_storage.delete_simulation_log(simulation.id)
    assert memgraph_storage.get_simulation_log(simulation.id) is None


def test_subplot_crud(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    subplot_cls = helpers.get_schema_model("Subplot")
    subplot = subplot_cls(
        id=f"subplot-{uuid4()}",
        root_id=root_id,
        branch_id=branch_id,
        title="subplot",
        subplot_type="mystery",
        protagonist_id="entity-1",
        central_conflict="conflict",
    )

    memgraph_storage.create_subplot(subplot)
    loaded = memgraph_storage.get_subplot(subplot.id)
    assert loaded is not None
    assert loaded.status == "dormant"
    assert loaded.root_id == root_id
    assert loaded.branch_id == branch_id
    assert loaded.protagonist_id == "entity-1"
    assert loaded.central_conflict == "conflict"

    subplot.status = "active"
    memgraph_storage.update_subplot(subplot)
    updated = memgraph_storage.get_subplot(subplot.id)
    assert updated is not None
    assert updated.status == "active"

    subplot.status = "resolved"
    memgraph_storage.update_subplot(subplot)
    resolved = memgraph_storage.get_subplot(subplot.id)
    assert resolved is not None
    assert resolved.status == "resolved"

    memgraph_storage.delete_subplot(subplot.id)
    assert memgraph_storage.get_subplot(subplot.id) is None

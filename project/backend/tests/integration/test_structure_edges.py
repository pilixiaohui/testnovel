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
        missing = exc.name
        if missing in {"gqlalchemy"}:
            pytest.fail(
                f"{module_path} requires {missing} but it is missing: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        message = str(exc)
        if "gqlalchemy" in message:
            pytest.fail(
                f"{module_path} dependency import failed: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_schema_model(name: str):
    module = _import_module("app.storage.schema")
    if not hasattr(module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    return getattr(module, name)


def _edge_count(storage, rel_type: str, from_label: str, from_id: str, to_label: str, to_id: str) -> int:
    record = next(
        storage.db.execute_and_fetch(
            f"MATCH (from:{from_label} {{id: $from_id}})"
            f"-[r:{rel_type}]->"
            f"(to:{to_label} {{id: $to_id}}) "
            "RETURN count(r) AS count;",
            {"from_id": from_id, "to_id": to_id},
        ),
        None,
    )
    if record is None:
        pytest.fail(f"{rel_type} edge query returned no result", pytrace=False)
    return int(record["count"])


def _assert_edge(storage, rel_type: str, from_label: str, from_id: str, to_label: str, to_id: str) -> None:
    count = _edge_count(storage, rel_type, from_label, from_id, to_label, to_id)
    assert (
        count == 1
    ), f"{rel_type} edge missing between {from_label}:{from_id} and {to_label}:{to_id}"


def _assert_unique_outgoing_edge(storage, rel_type: str, from_label: str, from_id: str) -> None:
    record = next(
        storage.db.execute_and_fetch(
            f"MATCH (from:{from_label} {{id: $from_id}})-[r:{rel_type}]->() "
            "RETURN count(r) AS count;",
            {"from_id": from_id},
        ),
        None,
    )
    if record is None:
        pytest.fail(f"{rel_type} edge query returned no result", pytrace=False)
    assert (
        int(record["count"]) == 1
    ), f"{rel_type} edge count mismatch for {from_label}:{from_id}"


def _get_default_branch_id() -> str:
    module = _import_module("app.constants")
    if not hasattr(module, "DEFAULT_BRANCH_ID"):
        pytest.fail("DEFAULT_BRANCH_ID is missing", pytrace=False)
    return module.DEFAULT_BRANCH_ID


def _seed_root_branch_head(memgraph_storage, *, root_id: str, branch_id: str, seed_commit_id: str) -> str:
    root_cls = _get_schema_model("Root")
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")

    memgraph_storage.create_root(
        root_cls(
            id=root_id,
            logline="seed",
            theme="seed",
            ending="seed",
            created_at="2024-01-01T00:00:00Z",
        )
    )
    memgraph_storage.create_branch(
        branch_cls(
            id=f"{root_id}:{branch_id}",
            root_id=root_id,
            branch_id=branch_id,
            parent_branch_id=None,
            fork_scene_origin_id=None,
            fork_commit_id=None,
        )
    )
    memgraph_storage.create_commit(
        commit_cls(
            id=seed_commit_id,
            parent_id=None,
            message="seed",
            created_at="2024-01-01T00:00:00Z",
            root_id=root_id,
            branch_id=branch_id,
        )
    )
    branch_head_id = f"{root_id}:{branch_id}:head"
    memgraph_storage.create_branch_head(
        branch_head_cls(
            id=branch_head_id,
            root_id=root_id,
            branch_id=branch_id,
            head_commit_id=seed_commit_id,
            version=1,
        )
    )
    return branch_head_id


def _seed_branch_head(
    memgraph_storage,
    *,
    root_id: str,
    branch_id: str,
    parent_branch_id: str,
    parent_commit_id: str,
) -> tuple[str, str]:
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")

    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    memgraph_storage.create_branch(
        branch_cls(
            id=f"{root_id}:{branch_id}",
            root_id=root_id,
            branch_id=branch_id,
            parent_branch_id=parent_branch_id,
            fork_scene_origin_id=None,
            fork_commit_id=parent_commit_id,
        )
    )
    memgraph_storage.create_commit(
        commit_cls(
            id=commit_id,
            parent_id=parent_commit_id,
            message="seed branch",
            created_at="2024-01-01T00:00:00Z",
            root_id=root_id,
            branch_id=branch_id,
        )
    )
    branch_head_id = f"{root_id}:{branch_id}:head"
    memgraph_storage.create_branch_head(
        branch_head_cls(
            id=branch_head_id,
            root_id=root_id,
            branch_id=branch_id,
            head_commit_id=commit_id,
            version=1,
        )
    )
    return commit_id, branch_head_id


def _scene_content(summary: str) -> dict:
    return {
        "expected_outcome": "stay",
        "conflict_type": "internal",
        "actual_outcome": "stay",
        "summary": summary,
        "rendered_content": f"{summary} render",
        "pov_character_id": "pov-1",
        "status": "draft",
    }


def _fetch_scene_version_props(storage, *, scene_origin_id: str, commit_id: str) -> dict:
    record = next(
        storage.db.execute_and_fetch(
            "MATCH (sv:SceneVersion {scene_origin_id: $scene_origin_id, commit_id: $commit_id}) "
            "RETURN sv LIMIT 1;",
            {"scene_origin_id": scene_origin_id, "commit_id": commit_id},
        ),
        None,
    )
    if record is None:
        pytest.fail("scene version record not found", pytrace=False)
    return record["sv"]._properties


def test_structure_edges_on_scene_origin_flow(memgraph_storage):
    root_cls = _get_schema_model("Root")
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    branch_node_id = f"{root_id}:{branch_id}"
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"

    memgraph_storage.create_root(
        root_cls(
            id=root_id,
            logline="seed",
            theme="seed",
            ending="seed",
            created_at="2024-01-01T00:00:00Z",
        )
    )
    memgraph_storage.create_branch(
        branch_cls(
            id=branch_node_id,
            root_id=root_id,
            branch_id=branch_id,
            parent_branch_id=None,
            fork_scene_origin_id=None,
            fork_commit_id=None,
        )
    )
    memgraph_storage.create_commit(
        commit_cls(
            id=seed_commit_id,
            parent_id=None,
            message="seed",
            created_at="2024-01-01T00:00:00Z",
            root_id=root_id,
            branch_id=branch_id,
        )
    )
    branch_head_id = f"{root_id}:{branch_id}:head"
    memgraph_storage.create_branch_head(
        branch_head_cls(
            id=branch_head_id,
            root_id=root_id,
            branch_id=branch_id,
            head_commit_id=seed_commit_id,
            version=1,
        )
    )

    content = {
        "expected_outcome": "stay",
        "conflict_type": "internal",
        "actual_outcome": "stay",
        "summary": "seed summary",
        "rendered_content": "seed render",
        "pov_character_id": "pov-1",
        "status": "draft",
    }
    created = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
        content=content,
    )

    commit_id = created["commit_id"]
    scene_origin_id = created["scene_origin_id"]
    scene_version_id = created["scene_version_id"]

    assert memgraph_storage.get_commit(commit_id) is not None
    assert memgraph_storage.get_scene_origin(scene_origin_id) is not None
    assert memgraph_storage.get_scene_version(scene_version_id) is not None

    _assert_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id, "Commit", commit_id)
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id)
    _assert_edge(memgraph_storage, "PARENT", "Commit", commit_id, "Commit", seed_commit_id)
    _assert_edge(
        memgraph_storage, "INCLUDES", "Commit", commit_id, "SceneVersion", scene_version_id
    )
    _assert_edge(
        memgraph_storage,
        "OF_ORIGIN",
        "SceneVersion",
        scene_version_id,
        "SceneOrigin",
        scene_origin_id,
    )


def test_structure_edges_branch_head_moves_and_commit_chain(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    branch_head_id = _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    first = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
        content=_scene_content("first"),
    )
    second = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 2",
        content=_scene_content("second"),
    )

    _assert_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id, "Commit", second["commit_id"])
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id)
    assert (
        _edge_count(
            memgraph_storage,
            "HEAD",
            "BranchHead",
            branch_head_id,
            "Commit",
            first["commit_id"],
        )
        == 0
    )
    _assert_edge(memgraph_storage, "PARENT", "Commit", first["commit_id"], "Commit", seed_commit_id)
    _assert_edge(memgraph_storage, "PARENT", "Commit", second["commit_id"], "Commit", first["commit_id"])

    first_origin = memgraph_storage.get_scene_origin(first["scene_origin_id"])
    second_origin = memgraph_storage.get_scene_origin(second["scene_origin_id"])
    assert first_origin is not None
    assert second_origin is not None
    assert first_origin.sequence_index == 1
    assert second_origin.sequence_index == 2


def test_structure_edges_delete_scene_origin_updates_head_and_cleans_versions(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    branch_head_id = _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    created = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene delete",
        content=_scene_content("delete"),
    )
    result = memgraph_storage.delete_scene_origin(
        created["scene_origin_id"],
        root_id=root_id,
        branch_id=branch_id,
        message="remove scene",
    )
    assert result is not None
    assert created["scene_version_id"] in result["scene_version_ids"]
    assert memgraph_storage.get_scene_origin(created["scene_origin_id"]) is None
    assert memgraph_storage.get_scene_version(created["scene_version_id"]) is None
    _assert_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id, "Commit", result["commit_id"])
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id)

    scene_origin_cls = _get_schema_model("SceneOrigin")
    manual_origin = scene_origin_cls(
        id=str(uuid4()),
        root_id=root_id,
        title="Manual",
        initial_commit_id=seed_commit_id,
        sequence_index=7,
        parent_act_id=None,
    )
    memgraph_storage.create_scene_origin(manual_origin)
    assert memgraph_storage.get_scene_origin(manual_origin.id) is not None
    memgraph_storage.delete_scene_origin(manual_origin.id)
    assert memgraph_storage.get_scene_origin(manual_origin.id) is None


def test_structure_edges_crud_roundtrip(memgraph_storage):
    root_cls = _get_schema_model("Root")
    branch_cls = _get_schema_model("Branch")
    branch_head_cls = _get_schema_model("BranchHead")
    commit_cls = _get_schema_model("Commit")
    scene_origin_cls = _get_schema_model("SceneOrigin")
    scene_version_cls = _get_schema_model("SceneVersion")
    entity_cls = _get_schema_model("Entity")
    snapshot_cls = _get_schema_model("WorldSnapshot")

    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"

    root = root_cls(
        id=root_id,
        logline="seed",
        theme="seed",
        ending="seed",
        created_at="2024-01-01T00:00:00Z",
    )
    memgraph_storage.create_root(root)
    assert memgraph_storage.get_root(root_id) is not None
    root.logline = "updated"
    memgraph_storage.update_root(root)

    branch = branch_cls(
        id=f"{root_id}:{branch_id}",
        root_id=root_id,
        branch_id=branch_id,
        parent_branch_id=None,
        fork_scene_origin_id=None,
        fork_commit_id=None,
    )
    memgraph_storage.create_branch(branch)
    branch.parent_branch_id = "parent"
    memgraph_storage.update_branch(branch)

    commit = commit_cls(
        id=seed_commit_id,
        parent_id=None,
        message="seed",
        created_at="2024-01-01T00:00:00Z",
        root_id=root_id,
        branch_id=branch_id,
    )
    memgraph_storage.create_commit(commit)
    commit.message = "updated"
    memgraph_storage.update_commit(commit)

    branch_head_id = f"{root_id}:{branch_id}:head"
    branch_head = branch_head_cls(
        id=branch_head_id,
        root_id=root_id,
        branch_id=branch_id,
        head_commit_id=seed_commit_id,
        version=1,
    )
    memgraph_storage.create_branch_head(branch_head)
    branch_head.version = 2
    memgraph_storage.update_branch_head(branch_head)

    scene_origin = scene_origin_cls(
        id=str(uuid4()),
        root_id=root_id,
        title="Origin",
        initial_commit_id=seed_commit_id,
        sequence_index=1,
        parent_act_id=None,
    )
    memgraph_storage.create_scene_origin(scene_origin)
    scene_origin.title = "Origin updated"
    memgraph_storage.update_scene_origin(scene_origin)

    scene_version = scene_version_cls(
        id=f"{scene_origin.id}:{uuid4()}",
        scene_origin_id=scene_origin.id,
        commit_id=seed_commit_id,
        pov_character_id="pov-1",
        status="draft",
        expected_outcome="stay",
        conflict_type="internal",
        actual_outcome="stay",
        summary="summary",
        rendered_content="render",
        logic_exception=False,
        logic_exception_reason=None,
        dirty=False,
    )
    memgraph_storage.create_scene_version(scene_version)
    scene_version.summary = "updated"
    memgraph_storage.update_scene_version(scene_version)

    entity = entity_cls(
        id=str(uuid4()),
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
        name="Hero",
        tags=["tag"],
        semantic_states={},
        arc_status="active",
    )
    memgraph_storage.create_entity(entity)
    entity.name = "Hero updated"
    memgraph_storage.update_entity(entity)

    snapshot = snapshot_cls(
        id=str(uuid4()),
        scene_version_id=scene_version.id,
        branch_id=branch_id,
        scene_seq=1,
        entity_states={},
        relations=[],
    )
    memgraph_storage.create_world_snapshot(snapshot)
    snapshot.entity_states = {"entity": {"state": "ok"}}
    memgraph_storage.update_world_snapshot(snapshot)

    memgraph_storage.delete_scene_version(scene_version.id)
    memgraph_storage.delete_scene_origin(scene_origin.id)
    memgraph_storage.delete_entity(entity.id)
    memgraph_storage.delete_world_snapshot(snapshot.id)
    memgraph_storage.delete_branch_head(branch_head_id)
    memgraph_storage.delete_commit(seed_commit_id)
    memgraph_storage.delete_branch(branch.id)
    memgraph_storage.delete_root(root_id)


def test_structure_edges_branch_management_and_history(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    memgraph_storage.create_branch(root_id=root_id, branch_id="feature")
    branches = memgraph_storage.list_branches(root_id=root_id)
    assert set(branches) >= {branch_id, "feature"}
    memgraph_storage.require_branch(root_id=root_id, branch_id="feature")
    memgraph_storage.merge_branch(root_id=root_id, branch_id="feature")
    memgraph_storage.revert_branch(root_id=root_id, branch_id="feature")

    created = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene fork",
        content=_scene_content("fork"),
    )
    memgraph_storage.fork_from_commit(
        root_id=root_id,
        source_commit_id=created["commit_id"],
        new_branch_id="forked",
        parent_branch_id=branch_id,
        fork_scene_origin_id=created["scene_origin_id"],
    )
    memgraph_storage.fork_from_scene(
        root_id=root_id,
        source_branch_id=branch_id,
        scene_origin_id=created["scene_origin_id"],
        new_branch_id="forked-from-scene",
        commit_id=created["commit_id"],
    )

    memgraph_storage.reset_branch_head(
        root_id=root_id,
        branch_id=branch_id,
        commit_id=seed_commit_id,
    )
    history = memgraph_storage.get_branch_history(root_id=root_id, branch_id=branch_id, limit=10)
    assert any(entry["id"] == seed_commit_id for entry in history)

    memgraph_storage.require_root(root_id=root_id, branch_id=branch_id)
    gc_result = memgraph_storage.gc_orphan_commits(retention_days=30)
    assert set(gc_result.keys()) == {"deleted_commit_ids", "deleted_scene_version_ids"}


def test_structure_edges_merge_moves_parent_head(memgraph_storage):
    root_id = f"root-{uuid4()}"
    parent_branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{parent_branch_id}:{uuid4()}"
    parent_head_id = _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=parent_branch_id,
        seed_commit_id=seed_commit_id,
    )

    feature_commit_id, _ = _seed_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id="feature",
        parent_branch_id=parent_branch_id,
        parent_commit_id=seed_commit_id,
    )

    memgraph_storage.merge_branch(root_id=root_id, branch_id="feature")

    parent_head = memgraph_storage.get_branch_head(parent_head_id)
    assert parent_head is not None
    assert parent_head.head_commit_id == feature_commit_id
    _assert_edge(memgraph_storage, "HEAD", "BranchHead", parent_head_id, "Commit", feature_commit_id)
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", parent_head_id)
    _assert_edge(memgraph_storage, "PARENT", "Commit", feature_commit_id, "Commit", seed_commit_id)


def test_structure_edges_revert_moves_branch_head(memgraph_storage):
    root_id = f"root-{uuid4()}"
    parent_branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{parent_branch_id}:{uuid4()}"
    _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=parent_branch_id,
        seed_commit_id=seed_commit_id,
    )

    feature_commit_id, feature_head_id = _seed_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id="feature",
        parent_branch_id=parent_branch_id,
        parent_commit_id=seed_commit_id,
    )

    memgraph_storage.revert_branch(root_id=root_id, branch_id="feature")

    feature_head = memgraph_storage.get_branch_head(feature_head_id)
    assert feature_head is not None
    assert feature_head.head_commit_id == seed_commit_id
    _assert_edge(memgraph_storage, "HEAD", "BranchHead", feature_head_id, "Commit", seed_commit_id)
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", feature_head_id)
    _assert_edge(memgraph_storage, "PARENT", "Commit", feature_commit_id, "Commit", seed_commit_id)


def test_structure_edges_reset_moves_branch_head(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    branch_head_id = _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    created = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene reset",
        content=_scene_content("reset"),
    )
    memgraph_storage.reset_branch_head(
        root_id=root_id,
        branch_id=branch_id,
        commit_id=seed_commit_id,
    )

    head = memgraph_storage.get_branch_head(branch_head_id)
    assert head is not None
    assert head.head_commit_id == seed_commit_id
    _assert_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id, "Commit", seed_commit_id)
    _assert_unique_outgoing_edge(memgraph_storage, "HEAD", "BranchHead", branch_head_id)
    _assert_edge(memgraph_storage, "PARENT", "Commit", created["commit_id"], "Commit", seed_commit_id)


def test_structure_edges_scene_updates_and_flags(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    branch_head_id = _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    created = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene commit",
        content=_scene_content("commit-base"),
    )
    head = memgraph_storage.get_branch_head(branch_head_id)
    assert head is not None

    with pytest.raises(ValueError, match="branch head version mismatch"):
        memgraph_storage.commit_scene(
            root_id=root_id,
            branch_id=branch_id,
            scene_origin_id=created["scene_origin_id"],
            content=_scene_content("bad"),
            message="bad",
            expected_head_version=head.version + 10,
        )

    with pytest.raises(ValueError, match="expected_outcome is required"):
        memgraph_storage.commit_scene(
            root_id=root_id,
            branch_id=branch_id,
            scene_origin_id=created["scene_origin_id"],
            content={"conflict_type": "internal", "actual_outcome": "stay"},
            message="bad-content",
            expected_head_version=head.version,
        )

    first_commit = memgraph_storage.commit_scene(
        root_id=root_id,
        branch_id=branch_id,
        scene_origin_id=created["scene_origin_id"],
        content=_scene_content("first-commit"),
        message="first",
        expected_head_version=head.version,
    )
    second_commit = memgraph_storage.commit_scene(
        root_id=root_id,
        branch_id=branch_id,
        scene_origin_id=created["scene_origin_id"],
        content=_scene_content("second-commit"),
        message="second",
    )

    diff = memgraph_storage.diff_scene_versions(
        scene_origin_id=created["scene_origin_id"],
        from_commit_id=first_commit["commit_id"],
        to_commit_id=second_commit["commit_id"],
    )
    assert diff["summary"]["from"] != diff["summary"]["to"]

    memgraph_storage.save_scene_render(
        scene_id=created["scene_origin_id"],
        branch_id=branch_id,
        content="rendered",
    )
    render_props = _fetch_scene_version_props(
        memgraph_storage,
        scene_origin_id=created["scene_origin_id"],
        commit_id=second_commit["commit_id"],
    )
    assert render_props.get("rendered_content") == "rendered"

    memgraph_storage.complete_scene(
        scene_id=created["scene_origin_id"],
        branch_id=branch_id,
        actual_outcome="resolved",
        summary="done",
    )
    complete_props = _fetch_scene_version_props(
        memgraph_storage,
        scene_origin_id=created["scene_origin_id"],
        commit_id=second_commit["commit_id"],
    )
    assert complete_props.get("status") == "committed"

    memgraph_storage.mark_scene_logic_exception(
        root_id=root_id,
        branch_id=branch_id,
        scene_id=created["scene_origin_id"],
        reason="logic",
    )
    assert memgraph_storage.is_scene_logic_exception(
        root_id=root_id,
        branch_id=branch_id,
        scene_id=created["scene_origin_id"],
    )

    memgraph_storage.mark_scene_dirty(scene_id=created["scene_origin_id"], branch_id=branch_id)
    assert created["scene_origin_id"] in memgraph_storage.list_dirty_scenes(
        root_id=root_id,
        branch_id=branch_id,
    )

    memgraph_storage.apply_local_scene_fix(
        root_id=root_id,
        branch_id=branch_id,
        scene_id=created["scene_origin_id"],
    )

    future = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene future",
        content=_scene_content("future"),
    )
    future_ids = memgraph_storage.mark_future_scenes_dirty(
        root_id=root_id,
        branch_id=branch_id,
        scene_id=created["scene_origin_id"],
    )
    assert future["scene_origin_id"] in future_ids


def test_structure_edges_entities_relations_and_context(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = _get_default_branch_id()
    seed_commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    _seed_root_branch_head(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        seed_commit_id=seed_commit_id,
    )

    first_scene = memgraph_storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
        content=_scene_content("scene-alpha"),
    )

    scene_origin_cls = _get_schema_model("SceneOrigin")
    scene_version_cls = _get_schema_model("SceneVersion")
    entity_cls = _get_schema_model("Entity")

    scene_seq_10 = scene_origin_cls(
        id=str(uuid4()),
        root_id=root_id,
        title="Scene 10",
        initial_commit_id=seed_commit_id,
        sequence_index=10,
        parent_act_id=None,
    )
    memgraph_storage.create_scene_origin(scene_seq_10)
    scene_version = scene_version_cls(
        id=f"{scene_seq_10.id}:{uuid4()}",
        scene_origin_id=scene_seq_10.id,
        commit_id=seed_commit_id,
        pov_character_id="pov-1",
        status="draft",
        expected_outcome="stay",
        conflict_type="internal",
        actual_outcome="stay",
        summary="summary",
        rendered_content=None,
        logic_exception=False,
        logic_exception_reason=None,
        dirty=False,
    )
    memgraph_storage.create_scene_version(scene_version)

    hero = entity_cls(
        id=str(uuid4()),
        root_id=root_id,
        branch_id=branch_id,
        entity_type="Character",
        name="Hero",
        tags=[],
        semantic_states={},
        arc_status="active",
    )
    memgraph_storage.create_entity(hero)
    ally_id = memgraph_storage.create_entity(
        root_id=root_id,
        branch_id=branch_id,
        name="Ally",
        entity_type="Character",
        tags=["friend"],
        arc_status="active",
        semantic_states={},
    )

    entities = memgraph_storage.list_entities(root_id=root_id, branch_id=branch_id)
    assert len(entities) == 2
    assert memgraph_storage.get_entity_semantic_states(
        root_id=root_id,
        branch_id=branch_id,
        entity_id=hero.id,
    ) == {}

    updated_states = memgraph_storage.apply_semantic_states_patch(
        root_id=root_id,
        branch_id=branch_id,
        entity_id=hero.id,
        patch={"mood": "calm"},
    )
    assert updated_states["mood"] == "calm"

    memgraph_storage.upsert_entity_relation(
        root_id=root_id,
        branch_id=branch_id,
        from_entity_id=hero.id,
        to_entity_id=ally_id,
        relation_type="ALLY",
        tension=5,
    )

    context_no_snapshot = memgraph_storage.get_scene_context(
        scene_id=first_scene["scene_origin_id"],
        branch_id=branch_id,
    )
    assert context_no_snapshot["branch_id"] == branch_id

    context_snapshot = memgraph_storage.get_scene_context(
        scene_id=scene_seq_10.id,
        branch_id=branch_id,
    )
    assert context_snapshot["relations"]

    root_snapshot = memgraph_storage.get_root_snapshot(root_id=root_id, branch_id=branch_id)
    assert root_snapshot["characters"]

    world_state = memgraph_storage.build_logic_check_world_state(
        root_id=root_id,
        branch_id=branch_id,
        scene_id=scene_seq_10.id,
    )
    assert world_state


def test_structure_edges_save_snowflake(memgraph_storage):
    class _Root:
        def __init__(self, logline: str, theme: str, ending: str) -> None:
            self.logline = logline
            self.theme = theme
            self.ending = ending

    class _Character:
        def __init__(
            self,
            entity_id: str,
            name: str,
            *,
            ambition: str,
            conflict: str,
            epiphany: str,
            voice_dna: str,
        ) -> None:
            self.entity_id = entity_id
            self.name = name
            self.ambition = ambition
            self.conflict = conflict
            self.epiphany = epiphany
            self.voice_dna = voice_dna

    class _Scene:
        def __init__(
            self,
            scene_id: str,
            title: str,
            sequence_index: int,
            *,
            parent_act_id: str | None,
            pov_character_id: str,
            expected_outcome: str,
            conflict_type: str,
            actual_outcome: str,
            logic_exception: bool,
            is_dirty: bool,
        ) -> None:
            self.id = scene_id
            self.title = title
            self.sequence_index = sequence_index
            self.parent_act_id = parent_act_id
            self.pov_character_id = pov_character_id
            self.expected_outcome = expected_outcome
            self.conflict_type = conflict_type
            self.actual_outcome = actual_outcome
            self.logic_exception = logic_exception
            self.is_dirty = is_dirty

    root = _Root(logline="logline", theme="theme", ending="ending")
    characters = [
        _Character(
            entity_id=str(uuid4()),
            name="Hero",
            ambition="守护师门",
            conflict="旧仇未了",
            epiphany="以义止戈",
            voice_dna="沉稳克制",
        ),
    ]
    scenes = [
        _Scene(
            scene_id=str(uuid4()),
            title="Scene 1",
            sequence_index=0,
            parent_act_id=None,
            pov_character_id=characters[0].entity_id,
            expected_outcome="stay",
            conflict_type="internal",
            actual_outcome="stay",
            logic_exception=False,
            is_dirty=False,
        )
    ]

    root_id = memgraph_storage.save_snowflake(root, characters, scenes)
    assert memgraph_storage.get_root(root_id) is not None


def test_structure_edges_bulk_insert_and_snapshot(memgraph_storage):
    nodes = [
        {
            "id": "node-1",
            "label": "Root",
            "properties": {"logline": "seed", "theme": "theme", "ending": "ending"},
        },
        {
            "id": "node-2",
            "label": "Branch",
            "properties": {"root_id": "node-1", "branch_id": "main"},
        },
    ]
    memgraph_storage.insert_nodes(nodes)
    edges = [
        {
            "id": "edge-1",
            "type": "REL",
            "from_id": "node-1",
            "to_id": "node-2",
            "properties": {"weight": 1},
        }
    ]
    memgraph_storage.insert_edges(edges)

    snapshot = memgraph_storage.snapshot()
    assert snapshot["nodes"]
    assert snapshot["edges"]

    memgraph_storage.delete_edges(["edge-1"])
    memgraph_storage.delete_nodes(["node-1", "node-2"])

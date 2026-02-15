from uuid import uuid4

import pytest

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


def _link_anchor_dependency(memgraph_storage, *, dependent_id: str, dependency_id: str) -> None:
    memgraph_storage.db.execute(
        "MATCH (a:StoryAnchor {id: $dependent_id}), (b:StoryAnchor {id: $dependency_id}) "
        "CREATE (a)-[:DEPENDS_ON]->(b);",
        {"dependent_id": dependent_id, "dependency_id": dependency_id},
    )


def test_anchor_flow_marks_achieved_and_advances(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    anchor_one = memgraph_storage.create_anchor(
        root_id=root_id,
        branch_id=branch_id,
        seq=1,
        type="inciting_incident",
        desc="anchor-1",
        constraint="hard",
        conditions="{}",
    )
    anchor_two = memgraph_storage.create_anchor(
        root_id=root_id,
        branch_id=branch_id,
        seq=2,
        type="midpoint",
        desc="anchor-2",
        constraint="soft",
        conditions="{}",
    )

    assert anchor_one["id"] == f"{root_id}:anchor:1"
    assert anchor_one["achieved"] is False

    next_anchor = memgraph_storage.get_next_unachieved_anchor(
        root_id=root_id,
        branch_id=branch_id,
    )
    assert next_anchor["id"] == anchor_one["id"]

    created_scene = helpers.create_scene_origin(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
    )
    scene_version_id = created_scene["scene_version_id"]

    updated = memgraph_storage.mark_anchor_achieved(
        anchor_id=anchor_one["id"],
        scene_version_id=scene_version_id,
    )
    assert updated["achieved"] is True

    record = helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:StoryAnchor {id: $anchor_id}) RETURN a.achieved AS achieved;",
        {"anchor_id": anchor_one["id"]},
    )
    assert record is not None
    assert record["achieved"] is True

    edge = helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:StoryAnchor {id: $anchor_id})-[:TRIGGERED_AT]->(sv:SceneVersion {id: $scene_version_id}) "
        "RETURN count(*) AS count;",
        {"anchor_id": anchor_one["id"], "scene_version_id": scene_version_id},
    )
    assert edge is not None
    assert edge["count"] == 1

    next_anchor = memgraph_storage.get_next_unachieved_anchor(
        root_id=root_id,
        branch_id=branch_id,
    )
    assert next_anchor["id"] == anchor_two["id"]

    with pytest.raises(ValueError):
        memgraph_storage.mark_anchor_achieved(
            anchor_id=anchor_one["id"],
            scene_version_id=scene_version_id,
        )


def test_get_next_unachieved_anchor_respects_dependencies(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    blocked_anchor = memgraph_storage.create_anchor(
        root_id=root_id,
        branch_id=branch_id,
        seq=1,
        type="inciting_incident",
        desc="anchor-blocked",
        constraint="hard",
        conditions="{}",
    )
    prereq_anchor = memgraph_storage.create_anchor(
        root_id=root_id,
        branch_id=branch_id,
        seq=2,
        type="midpoint",
        desc="anchor-prereq",
        constraint="soft",
        conditions="{}",
    )
    _link_anchor_dependency(
        memgraph_storage,
        dependent_id=blocked_anchor["id"],
        dependency_id=prereq_anchor["id"],
    )

    next_anchor = memgraph_storage.get_next_unachieved_anchor(
        root_id=root_id,
        branch_id=branch_id,
    )
    assert next_anchor["id"] == prereq_anchor["id"]

    created_scene = helpers.create_scene_origin(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
    )
    scene_version_id = created_scene["scene_version_id"]
    memgraph_storage.mark_anchor_achieved(
        anchor_id=prereq_anchor["id"],
        scene_version_id=scene_version_id,
    )

    next_anchor = memgraph_storage.get_next_unachieved_anchor(
        root_id=root_id,
        branch_id=branch_id,
    )
    assert next_anchor["id"] == blocked_anchor["id"]


def test_create_anchor_validates_types(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    with pytest.raises(ValueError):
        memgraph_storage.create_anchor(
            root_id=root_id,
            branch_id=branch_id,
            seq=1,
            type="invalid_type",
            desc="anchor",
            constraint="hard",
            conditions="{}",
        )

    with pytest.raises(ValueError):
        memgraph_storage.create_anchor(
            root_id=root_id,
            branch_id=branch_id,
            seq=1,
            type="inciting_incident",
            desc="anchor",
            constraint="invalid_constraint",
            conditions="{}",
        )

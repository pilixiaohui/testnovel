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


def test_create_act_and_list_ordered(memgraph_storage):
    root_id, _branch_id = _seed_root(memgraph_storage)

    act_two = memgraph_storage.create_act(
        root_id=root_id,
        seq=2,
        title="Act 2",
        purpose="purpose-2",
        tone="tense",
    )
    act_one = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose-1",
        tone="calm",
    )

    assert act_one["id"] == f"{root_id}:act:1"
    assert act_two["id"] == f"{root_id}:act:2"

    acts = memgraph_storage.list_acts(root_id=root_id)
    assert [item["sequence"] for item in acts] == [1, 2]


def test_create_act_rejects_duplicate_sequence(memgraph_storage):
    root_id, _branch_id = _seed_root(memgraph_storage)

    memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    with pytest.raises(KeyError):
        memgraph_storage.create_act(
            root_id=root_id,
            seq=1,
            title="Act 1 duplicate",
            purpose="purpose",
            tone="calm",
        )


def test_create_chapter_and_list_ordered(memgraph_storage):
    root_id, _branch_id = _seed_root(memgraph_storage)

    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )

    chapter_two = memgraph_storage.create_chapter(
        act_id=act["id"],
        seq=2,
        title="Chapter 2",
        focus="focus-2",
        pov_character_id=None,
    )
    chapter_one = memgraph_storage.create_chapter(
        act_id=act["id"],
        seq=1,
        title="Chapter 1",
        focus="focus-1",
        pov_character_id=None,
    )

    assert chapter_one["id"] == f"{act['id']}:ch:1"
    assert chapter_two["id"] == f"{act['id']}:ch:2"

    chapters = memgraph_storage.list_chapters(act_id=act["id"])
    assert [item["sequence"] for item in chapters] == [1, 2]


def test_link_scene_to_chapter_sets_chapter_id_and_edge(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    chapter = memgraph_storage.create_chapter(
        act_id=act["id"],
        seq=1,
        title="Chapter 1",
        focus="focus",
        pov_character_id=None,
    )
    created_scene = helpers.create_scene_origin(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
        parent_act_id=act["id"],
    )

    scene_id = created_scene["scene_origin_id"]
    memgraph_storage.link_scene_to_chapter(
        scene_id=scene_id,
        chapter_id=chapter["id"],
    )

    record = helpers.fetch_one(
        memgraph_storage,
        "MATCH (s:SceneOrigin {id: $scene_id}) RETURN s.chapter_id AS chapter_id;",
        {"scene_id": scene_id},
    )
    assert record is not None
    assert record["chapter_id"] == chapter["id"]

    edge = helpers.fetch_one(
        memgraph_storage,
        "MATCH (c:Chapter {id: $chapter_id})-[:CONTAINS_SCENE]->(s:SceneOrigin {id: $scene_id}) "
        "RETURN count(*) AS count;",
        {"chapter_id": chapter["id"], "scene_id": scene_id},
    )
    assert edge is not None
    assert edge["count"] == 1


def test_link_scene_to_chapter_requires_scene(memgraph_storage):
    root_id, _branch_id = _seed_root(memgraph_storage)

    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    chapter = memgraph_storage.create_chapter(
        act_id=act["id"],
        seq=1,
        title="Chapter 1",
        focus="focus",
        pov_character_id=None,
    )

    with pytest.raises(KeyError):
        memgraph_storage.link_scene_to_chapter(
            scene_id="missing-scene",
            chapter_id=chapter["id"],
        )


def test_link_scene_to_chapter_requires_chapter(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)

    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    created_scene = helpers.create_scene_origin(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        title="Scene 1",
        parent_act_id=act["id"],
    )

    with pytest.raises(KeyError):
        memgraph_storage.link_scene_to_chapter(
            scene_id=created_scene["scene_origin_id"],
            chapter_id="missing-chapter",
        )

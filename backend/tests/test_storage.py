import tempfile
from uuid import uuid4

from app.models import CharacterSheet, SceneNode, SnowflakeRoot
from app.storage.graph import GraphStorage


def test_graph_storage_persists_snowflake():
    tmpdir = tempfile.mkdtemp()
    storage = GraphStorage(db_path=f"{tmpdir}/snowflake.db")

    root = SnowflakeRoot(
        logline="Test story",
        three_disasters=["D1", "D2", "D3"],
        ending="End",
        theme="Testing",
    )
    characters = [
        CharacterSheet(
            entity_id=uuid4(),
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    scenes = [
        SceneNode(
            expected_outcome="Outcome 1",
            conflict_type="internal",
            parent_act_id=None,
        ),
        SceneNode(
            expected_outcome="Outcome 2",
            conflict_type="external",
            parent_act_id=None,
        ),
    ]

    root_id = storage.save_snowflake(root, characters, scenes)

    assert storage.count_scenes(root_id) == 2
    ids = storage.fetch_scene_ids(root_id)
    assert len(ids) == 2
    assert len(set(ids)) == 2

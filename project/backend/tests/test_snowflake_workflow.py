from unittest.mock import AsyncMock, Mock

import pytest

from app.logic.snowflake_manager import SnowflakeManager
from app.constants import DEFAULT_BRANCH_ID
from app.models import (
    CharacterSheet,
    CharacterValidationResult,
    SceneNode,
    SnowflakeRoot,
)


@pytest.mark.asyncio
async def test_step1_logline_count_ok():
    mock_engine = AsyncMock()
    mock_engine.generate_logline_options.return_value = [
        f"Option {idx}" for idx in range(10)
    ]

    manager = SnowflakeManager(engine=mock_engine)
    result = await manager.execute_step_1_logline("raw idea")

    assert len(result) == 10


@pytest.mark.asyncio
async def test_step1_logline_count_invalid():
    mock_engine = AsyncMock()
    mock_engine.generate_logline_options.return_value = ["Option"] * 9

    manager = SnowflakeManager(engine=mock_engine)

    with pytest.raises(ValueError):
        await manager.execute_step_1_logline("raw idea")


@pytest.mark.asyncio
async def test_step2_structure_returns_root():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_engine = AsyncMock()
    mock_engine.generate_root_structure.return_value = mock_root

    manager = SnowflakeManager(engine=mock_engine)
    result = await manager.execute_step_2_structure("selected logline")

    assert result == mock_root


@pytest.mark.asyncio
async def test_step3_character_generation():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )

    mock_chars = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        ),
        CharacterSheet(
            name="Villain",
            ambition="Destroy world",
            conflict="Hero",
            epiphany="None",
            voice_dna="Cold",
        ),
    ]

    mock_engine = AsyncMock()
    mock_engine.generate_characters.return_value = mock_chars
    mock_engine.validate_characters.return_value = CharacterValidationResult(
        valid=True, issues=[]
    )

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)
    result = await manager.execute_step_3_characters(mock_root)

    assert len(result) == 2
    assert result[0].name == "Hero"


@pytest.mark.asyncio
async def test_step3_character_validation_failure():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_engine = AsyncMock()
    mock_engine.generate_characters.return_value = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_engine.validate_characters.return_value = CharacterValidationResult(
        valid=False, issues=["ambition conflicts with theme"]
    )

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)

    with pytest.raises(ValueError):
        await manager.execute_step_3_characters(mock_root)


@pytest.mark.asyncio
async def test_step4_scene_generation():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_scenes = [
        SceneNode(
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 1",
            sequence_index=0,
            expected_outcome="Outcome 1",
            conflict_type="internal",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        )
    ]

    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)
    result = await manager.execute_step_4_scenes(mock_root, mock_characters)

    assert len(result) == 1
    assert result[0].expected_outcome == "Outcome 1"


@pytest.mark.asyncio
async def test_step4_scene_validation_duplicate_id():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    scene = SceneNode(
        branch_id=DEFAULT_BRANCH_ID,
        title="Scene 1",
        sequence_index=0,
        expected_outcome="Outcome 1",
        conflict_type="internal",
        actual_outcome="",
        parent_act_id=None,
        is_dirty=False,
    )
    # Force duplicate UUID
    duplicate_id = scene.id
    mock_scenes = [
        scene,
        SceneNode(
            id=duplicate_id,
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 2",
            sequence_index=1,
            expected_outcome="Outcome 2",
            conflict_type="external",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        ),
    ]

    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)

    with pytest.raises(ValueError):
        await manager.execute_step_4_scenes(mock_root, mock_characters)


@pytest.mark.asyncio
async def test_step4_scene_validation_expected_outcome_required():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_scenes = [
        SceneNode(
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 1",
            sequence_index=0,
            expected_outcome=" ",
            conflict_type="internal",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        )
    ]
    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)

    with pytest.raises(ValueError, match="expected_outcome"):
        await manager.execute_step_4_scenes(mock_root, mock_characters)


@pytest.mark.asyncio
async def test_step4_scene_validation_conflict_type_required():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_scenes = [
        SceneNode(
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 1",
            sequence_index=0,
            expected_outcome="Outcome 1",
            conflict_type=" ",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        )
    ]
    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=5)

    with pytest.raises(ValueError, match="conflict_type"):
        await manager.execute_step_4_scenes(mock_root, mock_characters)


@pytest.mark.asyncio
async def test_step4_scene_requires_characters_when_storage_present():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_scenes = [
        SceneNode(
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 1",
            sequence_index=0,
            expected_outcome="Outcome 1",
            conflict_type="internal",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        )
    ]
    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(
        engine=mock_engine, min_scenes=1, max_scenes=5, storage=Mock()
    )

    with pytest.raises(ValueError, match="characters is required"):
        await manager.execute_step_4_scenes(mock_root, [])


@pytest.mark.asyncio
async def test_step4_scene_validation_count_bounds():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_scenes = []

    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes

    manager = SnowflakeManager(engine=mock_engine, min_scenes=1, max_scenes=2)

    with pytest.raises(ValueError):
        await manager.execute_step_4_scenes(mock_root, mock_characters)


@pytest.mark.asyncio
async def test_step4_scene_persistence():
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]
    mock_scenes = [
        SceneNode(
            branch_id=DEFAULT_BRANCH_ID,
            title="Scene 1",
            sequence_index=0,
            expected_outcome="Outcome 1",
            conflict_type="internal",
            actual_outcome="",
            parent_act_id=None,
            is_dirty=False,
        )
    ]

    mock_engine = AsyncMock()
    mock_engine.generate_scene_list.return_value = mock_scenes
    mock_storage = Mock()
    mock_storage.save_snowflake.return_value = "root-abc"

    manager = SnowflakeManager(
        engine=mock_engine, min_scenes=1, max_scenes=5, storage=mock_storage
    )
    result = await manager.execute_step_4_scenes(mock_root, mock_characters)

    mock_storage.save_snowflake.assert_called_once_with(
        root=mock_root, characters=mock_characters, scenes=mock_scenes
    )
    assert manager.last_persisted_root_id == "root-abc"
    assert result == mock_scenes

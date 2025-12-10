import pytest
from uuid import uuid4
from pydantic import ValidationError

from app.models import CharacterSheet, SceneNode, SnowflakeRoot


def test_snowflake_root_validation():
    # 缺少 three_disasters/ending/theme 应抛出校验错误
    with pytest.raises(ValidationError):
        SnowflakeRoot(logline="仅有一句话")

    # three_disasters 长度不足应失败
    with pytest.raises(ValidationError):
        SnowflakeRoot(
            logline="完整信息",
            three_disasters=["A", "B"],
            ending="End",
            theme="Theme",
        )


def test_character_sheet_structure():
    char = CharacterSheet(
        entity_id=uuid4(),
        name="Neo",
        ambition="Find Truth",
        conflict="Agents",
        epiphany="I am the One",
        voice_dna="Stoic",
    )
    assert char.name == "Neo"
    assert char.entity_id

    # voice_dna 不可为空
    with pytest.raises(ValidationError):
        CharacterSheet(
            entity_id=uuid4(),
            name="Neo",
            ambition="Find Truth",
            conflict="Agents",
            epiphany="I am the One",
            voice_dna="",
        )


def test_scene_node_requires_expected_outcome():
    with pytest.raises(ValidationError):
        SceneNode(conflict_type="internal")


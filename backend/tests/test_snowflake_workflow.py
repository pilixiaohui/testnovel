import pytest

from app.logic.snowflake_manager import SnowflakeManager
from app.models import CharacterSheet, CharacterValidationResult, SnowflakeRoot


@pytest.mark.asyncio
async def test_step3_character_generation(mocker):
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

    mock_engine = mocker.AsyncMock()
    mock_engine.generate_characters.return_value = mock_chars
    mock_engine.validate_characters.return_value = CharacterValidationResult(
        valid=True, issues=[]
    )

    manager = SnowflakeManager(engine=mock_engine)
    result = await manager.execute_step_3_characters(mock_root)

    assert len(result) == 2
    assert result[0].name == "Hero"


@pytest.mark.asyncio
async def test_step3_character_validation_failure(mocker):
    mock_root = SnowflakeRoot(
        logline="Hero saves world",
        three_disasters=["A", "B", "C"],
        ending="Win",
        theme="Hope",
    )
    mock_engine = mocker.AsyncMock()
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

    manager = SnowflakeManager(engine=mock_engine)

    with pytest.raises(ValueError):
        await manager.execute_step_3_characters(mock_root)


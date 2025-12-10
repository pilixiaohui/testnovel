import pytest
from typing import List

from app.models import CharacterSheet, SceneNode, SnowflakeRoot
from app.services.llm_engine import LLMEngine


@pytest.mark.asyncio
async def test_generate_structure(mocker):
    mock_response = SnowflakeRoot(
        logline="Test story",
        three_disasters=["D1", "D2", "D3"],
        ending="End",
        theme="Testing",
    )

    mock_client = mocker.Mock()
    mock_client.chat.completions.create.return_value = mock_response

    engine = LLMEngine(client=mock_client)
    result = await engine.generate_root_structure("A hacker finds verification")

    assert isinstance(result, SnowflakeRoot)
    assert result.logline == "Test story"


@pytest.mark.asyncio
async def test_generate_scene_list(mocker):
    mock_scenes = [
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

    mock_client = mocker.Mock()
    mock_client.chat.completions.create.return_value = mock_scenes

    engine = LLMEngine(client=mock_client)
    root = SnowflakeRoot(
        logline="Test story",
        three_disasters=["D1", "D2", "D3"],
        ending="End",
        theme="Testing",
    )
    characters = []

    result = await engine.generate_scene_list(root, characters)

    assert len(result) == 2
    assert all(isinstance(node, SceneNode) for node in result)


@pytest.mark.asyncio
async def test_generate_scene_list_prompt_shape(mocker):
    engine = LLMEngine(client=None)
    root = SnowflakeRoot(
        logline="Test story",
        three_disasters=["D1", "D2", "D3"],
        ending="End",
        theme="Testing",
    )
    characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Growth",
            voice_dna="Bold",
        )
    ]
    mock_call = mocker.AsyncMock(return_value=[])
    engine._call_model = mock_call  # type: ignore[attr-defined]

    await engine.generate_scene_list(root, characters)

    mock_call.assert_awaited_once()
    kwargs = mock_call.await_args.kwargs
    assert kwargs["response_model"] == List[SceneNode]
    messages = kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "50-100 个场景节点" in messages[0]["content"]
    assert root.logline in messages[1]["content"]
    assert "characters:" in messages[1]["content"]

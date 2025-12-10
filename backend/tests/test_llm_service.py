import pytest

from app.models import SnowflakeRoot
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


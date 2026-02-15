import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest

from app.models import CharacterSheet, CharacterValidationResult, SnowflakeRoot
from app.services.llm_engine import LLMEngine


def test_build_client_uses_stubbed_dependencies(monkeypatch):
    fake_instructor = types.ModuleType("instructor")

    def from_gemini(model):
        return {"model": model}

    fake_instructor.from_gemini = from_gemini

    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("google.generativeai")

    class FakeModel:
        def __init__(self, name: str):
            self.name = name

    fake_genai.GenerativeModel = FakeModel
    fake_google.generativeai = fake_genai

    monkeypatch.setitem(sys.modules, "instructor", fake_instructor)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    engine = LLMEngine(model_name="fake-model")
    client = engine._build_client()
    assert client["model"].name == "fake-model"


def test_ensure_client_builds_when_missing(monkeypatch):
    engine = LLMEngine(client=None)
    stub_client = Mock()
    monkeypatch.setattr(engine, "_build_client", Mock(return_value=stub_client))

    assert engine._ensure_client() is stub_client


@pytest.mark.asyncio
async def test_generate_logline_options_awaits_async_create():
    mock_client = Mock()
    mock_client.chat = Mock()
    mock_client.chat.completions = Mock()
    mock_client.chat.completions.create = AsyncMock(return_value=["a", "b"])

    engine = LLMEngine(client=mock_client)
    result = await engine.generate_logline_options("idea")

    assert result == ["a", "b"]
    mock_client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_characters_builds_expected_prompt():
    engine = LLMEngine(client=Mock())
    mock_call = AsyncMock(return_value=[])
    engine._call_model = mock_call  # type: ignore[attr-defined]

    root = SnowflakeRoot(
        logline="Test story",
        three_disasters=["A", "B", "C"],
        ending="End",
        theme="Theme",
    )

    await engine.generate_characters(root)

    kwargs = mock_call.await_args.kwargs
    messages = kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert root.logline in messages[1]["content"]


@pytest.mark.asyncio
async def test_validate_characters_builds_expected_prompt():
    engine = LLMEngine(client=Mock())
    mock_call = AsyncMock(return_value=CharacterValidationResult(valid=True, issues=[]))
    engine._call_model = mock_call  # type: ignore[attr-defined]

    root = SnowflakeRoot(
        logline="Test story",
        three_disasters=["A", "B", "C"],
        ending="End",
        theme="Theme",
    )
    characters = [
        CharacterSheet(
            name="Hero",
            ambition="Save world",
            conflict="Weakness",
            epiphany="Strength",
            voice_dna="Bold",
        )
    ]

    result = await engine.validate_characters(root, characters)

    assert result.valid is True
    kwargs = mock_call.await_args.kwargs
    assert root.logline in kwargs["messages"][1]["content"]
    assert "characters:" in kwargs["messages"][1]["content"]

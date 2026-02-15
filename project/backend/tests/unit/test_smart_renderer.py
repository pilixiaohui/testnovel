from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models import ActionResult, AgentAction, DMArbitration, SimulationRoundResult
from app.services.smart_renderer import SmartRenderer


def _build_action_result() -> ActionResult:
    return ActionResult(
        action_id="act-1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="clear",
    )


def _build_dm_arbitration() -> DMArbitration:
    return DMArbitration(round_id="round-1", action_results=[_build_action_result()])


def _build_agent_action() -> AgentAction:
    return AgentAction(
        agent_id="agent-1",
        internal_thought="wait",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="pause",
    )


def _build_round(
    *,
    info_gain: float,
    narrative_events: list[dict[str, object]],
    sensory_seeds: list[dict[str, object]],
) -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=narrative_events,
        sensory_seeds=sensory_seeds,
        convergence_score=0.2,
        drama_score=0.3,
        info_gain=info_gain,
        stagnation_count=0,
    )


@pytest.mark.asyncio
async def test_render_calls_llm_with_beats_and_sensory():
    llm = AsyncMock()
    llm.generate_prose = AsyncMock(return_value="rendered")
    retrieval = AsyncMock()
    retrieval.get_style = AsyncMock(return_value={"tone": "tense"})

    renderer = SmartRenderer(llm=llm, retrieval_service=retrieval)

    rounds = [
        _build_round(
            info_gain=0.05,
            narrative_events=[{"event": "drop"}],
            sensory_seeds=[{"type": "weather", "detail": "fog"}],
        ),
        _build_round(
            info_gain=0.2,
            narrative_events=[{"event": "keep"}],
            sensory_seeds=[
                {"type": "weather", "detail": "rain"},
                {"type": "gesture", "detail": "tremble", "char_id": "c1"},
            ],
        ),
    ]
    scene = {"id": "scene-alpha", "pov_character_id": "c1"}

    content = await renderer.render(rounds, scene)

    assert content == "rendered"
    retrieval.get_style.assert_awaited_once_with(
        scene_id="scene-alpha",
        includes=["previous_foreshadowing", "character_voice", "tone"],
    )

    llm.generate_prose.assert_awaited_once()
    kwargs = llm.generate_prose.await_args.kwargs
    assert kwargs["beats"] == [{"event": "keep"}]
    assert kwargs["style"] == {"tone": "tense"}
    assert kwargs["pov"] == "c1"
    assert "weather" in kwargs["sensory"]
    assert any(seed.get("detail") == "rain" for seed in kwargs["sensory"]["weather"])
    assert "gesture" in kwargs["sensory"]
    assert any(seed.get("detail") == "tremble" for seed in kwargs["sensory"]["gesture"])


@pytest.mark.asyncio
async def test_check_continuity_errors_returns_structured_errors():
    renderer = SmartRenderer()

    scene = {"continuity_rules": {"character_locations": {"hero": "bridge"}}}
    errors = await renderer.check_continuity_errors("hero@castle", scene)

    assert isinstance(errors, list)
    assert any(error.get("type") == "character_location" for error in errors)

    ok = await renderer.check_continuity_errors("hero@bridge", scene)
    assert ok == []


@pytest.mark.asyncio
async def test_render_calls_fix_continuity_when_errors():
    llm = AsyncMock()
    llm.generate_prose = AsyncMock(return_value="hero@castle")
    retrieval = AsyncMock()
    retrieval.get_style = AsyncMock(return_value={})

    renderer = SmartRenderer(llm=llm, retrieval_service=retrieval)

    rounds = [
        _build_round(
            info_gain=0.2,
            narrative_events=[{"event": "move"}],
            sensory_seeds=[],
        )
    ]
    scene = {
        "id": "scene-alpha",
        "pov_character_id": "hero",
        "continuity_rules": {"character_locations": {"hero": "bridge"}},
    }

    content = await renderer.render(rounds, scene)

    assert content == "hero@bridge"
    errors = getattr(renderer, "_last_continuity_errors", None)
    assert errors
    assert errors[0]["type"] == "character_location"
    assert errors[0]["character_id"] == "hero"
    assert errors[0]["expected"] == "bridge"
    assert errors[0]["actual"] == "castle"


@pytest.mark.asyncio
async def test_render_skips_fix_continuity_when_no_errors():
    llm = AsyncMock()
    llm.generate_prose = AsyncMock(return_value="hero@bridge")
    retrieval = AsyncMock()
    retrieval.get_style = AsyncMock(return_value={})

    renderer = SmartRenderer(llm=llm, retrieval_service=retrieval)

    rounds = [
        _build_round(
            info_gain=0.2,
            narrative_events=[{"event": "move"}],
            sensory_seeds=[],
        )
    ]
    scene = {
        "id": "scene-alpha",
        "pov_character_id": "hero",
        "continuity_rules": {"character_locations": {"hero": "bridge"}},
    }

    content = await renderer.render(rounds, scene)

    assert content == "hero@bridge"
    assert not hasattr(renderer, "_last_continuity_errors")


@pytest.mark.asyncio
async def test_render_calls_llm_with_style_context_when_beats_empty():
    llm = AsyncMock()
    llm.generate_prose = AsyncMock(return_value="rendered")
    retrieval = AsyncMock()
    retrieval.get_style = AsyncMock(return_value={"tone": "calm"})

    renderer = SmartRenderer(llm=llm, retrieval_service=retrieval)

    rounds = [
        _build_round(
            info_gain=0.05,
            narrative_events=[{"event": "drop"}],
            sensory_seeds=[],
        )
    ]
    scene = {"id": "scene-2", "pov_character_id": "p2"}

    content = await renderer.render(rounds, scene)

    assert content == "rendered"
    retrieval.get_style.assert_awaited_once_with(
        scene_id="scene-2",
        includes=["previous_foreshadowing", "character_voice", "tone"],
    )
    llm.generate_prose.assert_awaited_once()
    kwargs = llm.generate_prose.await_args.kwargs
    assert kwargs["beats"] == []
    assert kwargs["style"] == {"tone": "calm"}
    assert kwargs["pov"] == "p2"

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import AgentAction, Intention
from app.services.character_agent import CharacterAgentEngine


def _build_intention() -> Intention:
    return Intention(
        id="intent-1",
        desire_id="desire-1",
        action_type="investigate",
        target="target-1",
        expected_outcome="clue",
        risk_assessment=0.3,
    )


def _build_desire(
    desire_id: str,
    *,
    priority: int,
    expires_at_scene: int | None,
) -> dict[str, object]:
    return {
        "id": desire_id,
        "type": "short_term",
        "description": "desc",
        "priority": priority,
        "satisfaction_condition": "condition",
        "created_at_scene": 1,
        "expires_at_scene": expires_at_scene,
    }


class _FakeStorage:
    def __init__(self, agent_state=None):
        self.agent_state = agent_state
        self.updated_beliefs: tuple[str, dict[str, object]] | None = None

    def get_agent_state(self, agent_id: str):
        _ = agent_id
        return self.agent_state

    def update_agent_beliefs(self, *, agent_id: str, beliefs_patch: dict[str, object]):
        self.updated_beliefs = (agent_id, beliefs_patch)
        return {"id": agent_id, "beliefs": beliefs_patch, "version": 2}


@pytest.mark.asyncio
async def test_act_returns_wait_when_no_intentions():
    llm = SimpleNamespace(generate_agent_action=AsyncMock())
    engine = CharacterAgentEngine(storage=object(), llm=llm)
    engine.deliberate = AsyncMock(return_value=[])

    action = await engine.act("agent-1", {"scene": "ctx"})

    assert action.action_type == "wait"
    assert action.agent_id == "agent-1"
    llm.generate_agent_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_act_uses_llm_when_intentions_present():
    expected = AgentAction(
        agent_id="agent-1",
        internal_thought="think",
        action_type="investigate",
        action_target="target-1",
        dialogue=None,
        action_description="search",
    )
    llm = SimpleNamespace(generate_agent_action=AsyncMock(return_value=expected))
    engine = CharacterAgentEngine(storage=object(), llm=llm)
    engine.deliberate = AsyncMock(return_value=[_build_intention()])

    action = await engine.act("agent-1", {"scene": "ctx"})

    assert action == expected
    llm.generate_agent_action.assert_awaited_once()
    args = llm.generate_agent_action.await_args.args
    assert args[0]["agent_id"] == "agent-1"


@pytest.mark.asyncio
async def test_perceive_updates_beliefs_from_llm_patch():
    beliefs_patch = {"world": {"location": "market"}, "others": {"npc-1": {"state": "alert"}}}
    llm = SimpleNamespace(
        generate_agent_perception=AsyncMock(return_value={"beliefs_patch": beliefs_patch})
    )
    storage = _FakeStorage()
    engine = CharacterAgentEngine(storage=storage, llm=llm)

    updated = await engine.perceive("agent-1", {"scene": "ctx"})

    llm.generate_agent_perception.assert_awaited_once()
    assert storage.updated_beliefs == ("agent-1", beliefs_patch)
    assert updated["beliefs"] == beliefs_patch


@pytest.mark.asyncio
async def test_deliberate_filters_and_sorts_desires_before_llm():
    desires = [
        _build_desire("d1", priority=1, expires_at_scene=2),
        _build_desire("d2", priority=9, expires_at_scene=None),
        _build_desire("d3", priority=4, expires_at_scene=5),
        _build_desire("d4", priority=8, expires_at_scene=3),
        _build_desire("d5", priority=10, expires_at_scene=100),
    ]
    agent_state = SimpleNamespace(
        desires=json.dumps(desires),
        last_updated_scene=3,
    )
    storage = _FakeStorage(agent_state=agent_state)
    expected = [_build_intention()]
    llm = SimpleNamespace(generate_agent_intentions=AsyncMock(return_value=expected))
    engine = CharacterAgentEngine(storage=storage, llm=llm)

    intentions = await engine.deliberate("agent-1")

    assert intentions == expected
    llm.generate_agent_intentions.assert_awaited_once()
    profile = llm.generate_agent_intentions.await_args.args[0]
    assert profile["agent_id"] == "agent-1"
    top_desires = profile["desires"]
    assert [item["id"] for item in top_desires] == ["d5", "d2", "d4"]


@pytest.mark.asyncio
async def test_act_rejects_missing_scene_context_preconditions():
    llm = SimpleNamespace(generate_agent_action=AsyncMock())
    engine = CharacterAgentEngine(storage=object(), llm=llm)
    engine.deliberate = AsyncMock(return_value=[_build_intention()])

    with pytest.raises(ValueError):
        await engine.act("agent-1", {})

    llm.generate_agent_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_decide_runs_perceive_deliberate_act_pipeline():
    expected = AgentAction(
        agent_id="agent-1",
        internal_thought="think",
        action_type="investigate",
        action_target="target-1",
        dialogue=None,
        action_description="search",
    )
    engine = CharacterAgentEngine(storage=object(), llm=object())
    engine.perceive = AsyncMock(return_value={"beliefs": {"world": "ok"}})
    engine.deliberate = AsyncMock(return_value=[_build_intention()])
    engine.act = AsyncMock(return_value=expected)

    action = await engine.decide("agent-1", {"scene": "ctx"})

    assert action == expected
    engine.perceive.assert_awaited_once_with("agent-1", {"scene": "ctx"})
    engine.deliberate.assert_awaited_once_with("agent-1")
    engine.act.assert_awaited_once_with("agent-1", {"scene": "ctx"})

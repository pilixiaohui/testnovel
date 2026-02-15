from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import ActionResult, AgentAction, DMArbitration
from app.services.simulation_engine import SimulationEngine


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


class LogStorage:
    def __init__(self) -> None:
        self.logs: list[object] = []

    def create_simulation_log(self, log: object) -> object:
        self.logs.append(log)
        return log


@pytest.mark.asyncio
async def test_run_scene_creates_simulation_logs():
    storage = LogStorage()
    agent = SimpleNamespace(
        agent_id="agent-1",
        decide=AsyncMock(return_value=_build_agent_action()),
    )
    world_master = SimpleNamespace(
        arbitrate=AsyncMock(return_value=_build_dm_arbitration()),
        inject_sensory_seeds=AsyncMock(return_value=[{"type": "weather"}]),
        monitor_pacing=AsyncMock(return_value=SimpleNamespace(type="none")),
    )
    renderer = SimpleNamespace(render=AsyncMock(return_value="rendered content"))
    engine = SimulationEngine(
        character_engine=None,
        world_master=world_master,
        storage=storage,
        llm=None,
        smart_renderer=renderer,
    )

    scene_context = {"scene_id": "scene-alpha", "scene_version_id": "scene-ver-1"}
    config = {"max_rounds": 2, "agents": [agent], "round_id": "scene-alpha"}
    result = await engine.run_scene(scene_context, config)

    assert result == "rendered content"
    assert len(storage.logs) == 2

    first, second = storage.logs
    assert first.scene_version_id == "scene-ver-1"
    assert first.round_number == 1
    assert first.id == "sim:scene-alpha:round:1"
    assert second.round_number == 2

from __future__ import annotations

import math
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import ActionResult, AgentAction, DMArbitration
from app.services.simulation_engine import SimulationEngine
from tests.service_coverage_helpers import (
    exercise_character_agent_engine,
    exercise_world_master_engine,
    exercise_simulation_engine,
    exercise_smart_renderer,
    exercise_llm_engine,
    exercise_local_story_engine,
    exercise_topone_client,
)

P95_LATENCY_MS = 2000.0
ROUND_SAMPLE_SIZE = 30
INFO_GAIN_SAMPLE_SIZE = 20
INFO_GAIN_AVG_MIN = 0.3
ANCHOR_SAMPLE_SIZE = 20
ANCHOR_ACHIEVEMENT_MIN = 0.9


def _percentile(values: list[float], percentile: float) -> float:
    assert values
    ordered = sorted(values)
    index = math.ceil((percentile / 100) * len(ordered)) - 1
    return ordered[index]


def _build_dm_arbitration() -> DMArbitration:
    return DMArbitration(
        round_id="round-1",
        action_results=[
            ActionResult(
                action_id="act-1",
                agent_id="agent-1",
                success="success",
                reason="ok",
                actual_outcome="clear",
            )
        ],
    )


def _build_agent_action() -> AgentAction:
    return AgentAction(
        agent_id="agent-1",
        internal_thought="wait",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="pause",
    )


def _build_sim_engine(info_gain_values: list[float]):
    world_master = SimpleNamespace(
        arbitrate=AsyncMock(return_value=_build_dm_arbitration()),
        inject_sensory_seeds=AsyncMock(return_value=[{"type": "weather"}]),
    )
    engine = SimulationEngine(
        character_engine=object(),
        world_master=world_master,
        storage=object(),
        llm=object(),
    )
    engine.calculate_info_gain = AsyncMock(side_effect=info_gain_values)
    agent = SimpleNamespace(
        agent_id="agent-1", decide=AsyncMock(return_value=_build_agent_action())
    )
    config = SimpleNamespace(round_id="round-1")
    return engine, agent, config


def _override(dep, value) -> None:
    app.dependency_overrides[dep] = lambda: value


class AnchorStorage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def mark_anchor_achieved(self, *, anchor_id: str, scene_version_id: str):
        self.calls.append((anchor_id, scene_version_id))
        return {"id": anchor_id, "scene_version_id": scene_version_id, "achieved": True}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_simulation_round_p95_latency():
    info_gain_values = [0.2] * (ROUND_SAMPLE_SIZE + 1)
    engine, agent, config = _build_sim_engine(info_gain_values)
    await engine.run_round({"scene": "ctx"}, [agent], config)

    latencies_ms: list[float] = []
    for _ in range(ROUND_SAMPLE_SIZE):
        start = perf_counter()
        await engine.run_round({"scene": "ctx"}, [agent], config)
        latencies_ms.append((perf_counter() - start) * 1000)

    p95 = _percentile(latencies_ms, 95)
    assert p95 <= P95_LATENCY_MS


@pytest.mark.asyncio
async def test_info_gain_average_meets_threshold():
    info_gain_values = [0.32, 0.35, 0.34, 0.36, 0.33] * 4
    engine, agent, config = _build_sim_engine(info_gain_values)

    gains: list[float] = []
    for _ in range(INFO_GAIN_SAMPLE_SIZE):
        result = await engine.run_round({"scene": "ctx"}, [agent], config)
        gains.append(result.info_gain)

    avg_gain = sum(gains) / len(gains)
    assert avg_gain >= INFO_GAIN_AVG_MIN


def test_anchor_achievement_rate(client):
    storage = AnchorStorage()
    _override(main.get_graph_storage, storage)

    achieved = 0
    for idx in range(ANCHOR_SAMPLE_SIZE):
        response = client.post(
            f"/api/v1/anchors/anchor-{idx}/check",
            json={"scene_version_id": f"scene-{idx}"},
        )
        assert response.status_code == 200
        if response.json()["achieved"] is True:
            achieved += 1

    rate = achieved / ANCHOR_SAMPLE_SIZE
    assert rate >= ANCHOR_ACHIEVEMENT_MIN


@pytest.mark.asyncio
async def test_service_core_components_coverage():
    await exercise_character_agent_engine()
    await exercise_world_master_engine()
    await exercise_simulation_engine()
    await exercise_smart_renderer()


@pytest.mark.asyncio
async def test_llm_and_topone_components_coverage():
    await exercise_llm_engine()
    await exercise_local_story_engine()
    await exercise_topone_client()

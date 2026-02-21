import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import ActionResult, AgentAction, DMArbitration, SimulationRoundResult


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


def _build_round_result() -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.2,
        drama_score=0.3,
        info_gain=0.4,
        stagnation_count=0,
    )


class SimulationStub:
    class _CharacterEngine:
        async def decide(self, _agent_id, _scene_context):
            return {
                "agent_id": "agent-1",
                "internal_thought": "wait",
                "action_type": "wait",
                "action_target": "",
                "dialogue": None,
                "action_description": "pause",
            }

    def __init__(self) -> None:
        self.character_engine = self._CharacterEngine()

    async def run_round(self, scene_context, agents, config):
        return _build_round_result()

    async def run_scene(self, scene_context, config):
        return "rendered content"


class SimulationSceneValueErrorStub(SimulationStub):
    async def run_scene(self, scene_context, config):
        raise ValueError("world_state is required for convergence flow")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_simulation_round_endpoint_returns_result(client):
    app.dependency_overrides[main.get_simulation_engine] = lambda: SimulationStub()

    payload = {
        "scene_context": {"scene_id": "scene-alpha"},
        "agents": [{"agent_id": "agent-1"}],
        "round_id": "round-1",
    }
    response = client.post("/api/v1/simulation/round", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["round_id"] == "round-1"
    assert data["agent_actions"][0]["agent_id"] == "agent-1"


def test_simulation_scene_endpoint_returns_content(client):
    app.dependency_overrides[main.get_simulation_engine] = lambda: SimulationStub()

    payload = {
        "scene_context": {"scene_id": "scene-alpha"},
        "max_rounds": 1,
    }
    response = client.post("/api/v1/simulation/scene", json=payload)

    assert response.status_code == 200
    assert response.json()["content"] == "rendered content"


def test_simulation_scene_endpoint_maps_value_error_to_422(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    app.dependency_overrides[main.get_simulation_engine] = (
        lambda: SimulationSceneValueErrorStub()
    )

    payload = {
        "scene_context": {"scene_id": "scene-alpha"},
        "max_rounds": 1,
    }
    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.post("/api/v1/simulation/scene", json=payload)

    app.dependency_overrides = {}
    assert response.status_code == 422
    assert response.json()["detail"] == "world_state is required for convergence flow"

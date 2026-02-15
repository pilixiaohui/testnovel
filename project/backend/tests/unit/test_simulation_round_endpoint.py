from fastapi.testclient import TestClient

from app.main import app, get_simulation_engine
from app.models import AgentAction, DMArbitration, SimulationRoundResult


class DummyCharacterEngine:
    async def decide(self, agent_id: str, scene_context: dict):
        return AgentAction(
            agent_id=agent_id,
            internal_thought="focus",
            action_type="wait",
            action_target="",
            dialogue=None,
            action_description="wait",
        )


class DummySimulationEngine:
    def __init__(self) -> None:
        self.character_engine = DummyCharacterEngine()

    async def run_round(self, scene_context: dict, agents, config):
        assert len(agents) == 1
        agent = agents[0]
        action = await agent.decide(agent.agent_id, scene_context)
        arbitration = DMArbitration(
            round_id=config.round_id,
            action_results=[],
            conflicts_resolved=[],
            environment_changes=[],
        )
        return SimulationRoundResult(
            round_id=config.round_id,
            agent_actions=[action],
            dm_arbitration=arbitration,
            narrative_events=[],
            sensory_seeds=[],
            convergence_score=0.0,
            drama_score=0.0,
            info_gain=0.0,
            stagnation_count=0,
        )


def test_simulation_round_accepts_agent_dict():
    engine = DummySimulationEngine()
    app.dependency_overrides[get_simulation_engine] = lambda: engine
    client = TestClient(app)

    response = client.post(
        "/api/v1/simulation/round",
        json={
            "scene_context": {"scene": {"summary": "setup"}},
            "agents": [{"id": "agent-alpha"}],
            "round_id": "round-alpha",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["round_id"] == "round-alpha"
    assert data["agent_actions"][0]["agent_id"] == "agent-alpha"

    app.dependency_overrides.clear()

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import ActionResult, AgentAction, DMArbitration, SimulationRoundResult
from tests.unit import models_contract_helpers as model_helpers


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


def _build_round_payload() -> dict[str, object]:
    round_result = SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.1,
        drama_score=0.3,
        info_gain=0.05,
        stagnation_count=3,
    )
    return round_result.model_dump()


class FeedbackStub:
    async def process_feedback(self, scene_context, rounds):
        FeedbackReport = model_helpers.require_model("FeedbackReport")
        report = FeedbackReport(
            trigger="stagnation",
            feedback={"info_gain": 0.05, "stagnation_count": 3},
            corrections=[{"action": "inject_incident"}],
            severity=0.8,
        )
        updated = dict(scene_context)
        updated.setdefault("events", []).append(
            {"type": "feedback", "action": "inject_incident"}
        )
        return report, updated


class FeedbackNoopStub:
    async def process_feedback(self, scene_context, rounds):
        return None, dict(scene_context)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_feedback_loop_endpoint_returns_report(client):
    app.dependency_overrides[main.get_feedback_detector] = lambda: FeedbackStub()

    payload = {
        "scene_context": {"scene_id": "scene-alpha", "events": []},
        "rounds": [_build_round_payload()],
    }
    response = client.post("/api/v1/feedback/loop", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["report"]["trigger"] == "stagnation"
    assert data["scene_context"]["events"][-1]["action"] == "inject_incident"


def test_feedback_loop_endpoint_returns_none_when_no_report(client):
    app.dependency_overrides[main.get_feedback_detector] = lambda: FeedbackNoopStub()

    payload = {
        "scene_context": {"scene_id": "scene-alpha", "events": []},
        "rounds": [_build_round_payload()],
    }
    response = client.post("/api/v1/feedback/loop", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["report"] is None
    assert data["scene_context"]["scene_id"] == "scene-alpha"
    assert data["scene_context"]["events"] == []

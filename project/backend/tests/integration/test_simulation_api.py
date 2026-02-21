import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from tests.shared_stubs import (
    SimulationEngineStub,
    SimulationEngineValueErrorStub,
)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_simulation_round_endpoint_returns_result(client):
    app.dependency_overrides[main.get_simulation_engine] = lambda: SimulationEngineStub()

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
    app.dependency_overrides[main.get_simulation_engine] = lambda: SimulationEngineStub()

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
        lambda: SimulationEngineValueErrorStub()
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

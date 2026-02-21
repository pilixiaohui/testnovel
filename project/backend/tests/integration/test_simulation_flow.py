from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from tests.shared_stubs import build_round_result


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_simulation_round_endpoint_calls_engine(client):
    character_engine = SimpleNamespace(decide=AsyncMock(return_value={"agent_id": "agent-1"}))
    engine = SimpleNamespace(
        run_round=AsyncMock(return_value=build_round_result()),
        character_engine=character_engine,
    )
    app.dependency_overrides[main.get_simulation_engine] = lambda: engine

    payload = {
        "scene_context": {"scene": "ctx"},
        "agents": [{"agent_id": "agent-1"}],
        "round_id": "round-1",
    }
    response = client.post("/api/v1/simulation/round", json=payload)

    assert response.status_code == 200
    assert response.json()["round_id"] == "round-1"

    engine.run_round.assert_awaited_once()
    args = engine.run_round.await_args.args
    assert args[0] == payload["scene_context"]
    assert getattr(args[2], "round_id") == "round-1"


def test_simulation_scene_endpoint_calls_engine(client):
    engine = SimpleNamespace(run_scene=AsyncMock(return_value="rendered scene"))
    app.dependency_overrides[main.get_simulation_engine] = lambda: engine

    payload = {"scene_context": {"scene": "ctx"}, "max_rounds": 2}
    response = client.post("/api/v1/simulation/scene", json=payload)

    assert response.status_code == 200
    assert response.json()["content"] == "rendered scene"

    engine.run_scene.assert_awaited_once()
    args = engine.run_scene.await_args.args
    assert args[0] == payload["scene_context"]
    assert getattr(args[1], "max_rounds") == 2


def test_render_scene_endpoint_uses_smart_renderer(client):
    renderer = SimpleNamespace(render=AsyncMock(return_value="rendered content"))
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer

    payload = {"rounds": [], "scene": {"id": "scene-alpha"}}
    response = client.post("/api/v1/render/scene", json=payload)

    assert response.status_code == 200
    assert response.json()["content"] == "rendered content"

    renderer.render.assert_awaited_once_with(payload["rounds"], payload["scene"])

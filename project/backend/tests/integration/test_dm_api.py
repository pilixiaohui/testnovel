from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import ReplanResult


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_dm_replan_success_returns_result(client):
    engine = SimpleNamespace(
        replan_route=AsyncMock(
            return_value=ReplanResult(
                success=True,
                new_chapters=[{"title": "bridge"}],
                modified_anchor=None,
                reason="recoverable",
            )
        )
    )
    app.dependency_overrides[main.get_world_master_engine] = lambda: engine

    payload = {
        "current_scene": "scene-alpha",
        "target_anchor": {"constraint_type": "hard", "required_conditions": ["cond"]},
        "world_state": {"state": 1},
    }
    response = client.post("/api/v1/dm/replan", json=payload)

    assert response.status_code == 200
    data = response.json()
    result = ReplanResult(**data)
    assert result.success is True
    assert result.new_chapters[0]["title"] == "bridge"
    assert result.modified_anchor is None
    assert result.reason == "recoverable"

    engine.replan_route.assert_awaited_once()
    args = engine.replan_route.await_args.args
    assert args[0] == payload["current_scene"]
    assert args[1] == payload["target_anchor"]
    assert args[2] == payload["world_state"]


def test_dm_replan_hard_anchor_unreachable_returns_422(client):
    engine = SimpleNamespace(
        replan_route=AsyncMock(
            return_value=ReplanResult(
                success=False,
                new_chapters=[],
                modified_anchor=None,
                reason="hard_anchor_unreachable",
            )
        )
    )
    app.dependency_overrides[main.get_world_master_engine] = lambda: engine

    payload = {
        "current_scene": "scene-alpha",
        "target_anchor": {"constraint_type": "hard", "required_conditions": ["cond"]},
        "world_state": {"state": 1},
    }
    response = client.post("/api/v1/dm/replan", json=payload)

    assert response.status_code == 422
    assert "hard_anchor_unreachable" in response.json()["detail"]

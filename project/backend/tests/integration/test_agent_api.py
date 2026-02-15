from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _desire_payload(priority: int = 5) -> dict[str, Any]:
    return {
        "id": "desire-1",
        "type": "short_term",
        "description": "secure safety",
        "priority": priority,
        "satisfaction_condition": "safe",
        "created_at_scene": 1,
        "expires_at_scene": None,
    }


class DesireStorage:
    def __init__(self) -> None:
        self.last_update: tuple[str, list[dict[str, Any]]] | None = None

    def update_agent_desires(
        self, *, agent_id: str, desires: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.last_update = (agent_id, desires)
        return {"id": agent_id, "desires": desires, "version": 2}


class MissingAgentStorage(DesireStorage):
    def update_agent_desires(
        self, *, agent_id: str, desires: list[dict[str, Any]]
    ) -> dict[str, Any]:
        _ = desires
        raise KeyError(f"agent state not found: {agent_id}")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_update_agent_desires_success(client):
    storage = DesireStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    payload = {"desires": [_desire_payload()]}
    response = client.put(
        "/api/v1/entities/char-1/agent/desires",
        params={"branch_id": "branch-1"},
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "agent:char-1:branch-1"
    assert data["desires"][0]["id"] == "desire-1"
    assert storage.last_update == ("agent:char-1:branch-1", payload["desires"])


def test_update_agent_desires_missing_agent_returns_404(client):
    storage = MissingAgentStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    payload = {"desires": [_desire_payload()]}
    response = client.put(
        "/api/v1/entities/char-1/agent/desires",
        params={"branch_id": "branch-1"},
        json=payload,
    )

    assert response.status_code == 404


def test_update_agent_desires_rejects_invalid_priority(client):
    storage = DesireStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    payload = {"desires": [_desire_payload(priority=0)]}
    response = client.put(
        "/api/v1/entities/char-1/agent/desires",
        params={"branch_id": "branch-1"},
        json=payload,
    )

    assert response.status_code == 422

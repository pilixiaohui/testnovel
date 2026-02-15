from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _root_payload() -> dict[str, object]:
    return {
        "logline": "A hero seeks redemption.",
        "three_disasters": ["loss", "betrayal", "reckoning"],
        "ending": "peace",
        "theme": "forgiveness",
    }


def _character_payload() -> dict[str, object]:
    return {
        "name": "Hero",
        "ambition": "redeem",
        "conflict": "guilt",
        "epiphany": "forgive",
        "voice_dna": "steady",
    }


class EmptyActStorage:
    def list_acts(self, *, root_id: str):
        _ = root_id
        return []


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_anchor_generation_requires_existing_acts(client):
    storage = EmptyActStorage()
    engine = SimpleNamespace(generate_story_anchors=AsyncMock())
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "branch_id": "branch-1",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/roots/root-alpha/anchors", json=payload)

    assert response.status_code == 400
    engine.generate_story_anchors.assert_not_awaited()

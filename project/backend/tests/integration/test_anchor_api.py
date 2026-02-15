from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app

REQUIRED_ANCHOR_TYPES = {
    "inciting_incident",
    "midpoint",
    "climax",
    "resolution",
}


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


def _build_anchor_list(count: int = 10) -> list[dict[str, object]]:
    anchors: list[dict[str, object]] = []
    required = list(REQUIRED_ANCHOR_TYPES)
    for idx in range(count):
        anchor_type = required[idx] if idx < len(required) else f"anchor_{idx}"
        anchors.append(
            {
                "anchor_type": anchor_type,
                "description": f"anchor-{idx}",
                "constraint_type": "hard",
                "required_conditions": [f"cond-{idx}"],
            }
        )
    return anchors


class AnchorStorage:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.acts: list[dict[str, object]] = [{"id": "act-1"}]
        self.list_anchors_called: tuple[str, str] | None = None
        self.anchors: list[dict[str, object]] = []
        self.list_acts_called: str | None = None

    def list_acts(self, *, root_id: str) -> list[dict[str, object]]:
        self.list_acts_called = root_id
        return list(self.acts)

    def create_anchor(
        self,
        *,
        root_id: str,
        branch_id: str,
        seq: int,
        type: str,
        desc: str,
        constraint: str,
        conditions: str,
    ) -> dict[str, object]:
        record = {
            "id": f"{root_id}:anchor:{seq}",
            "root_id": root_id,
            "branch_id": branch_id,
            "sequence": seq,
            "anchor_type": type,
            "description": desc,
            "constraint_type": constraint,
            "required_conditions": conditions,
            "deadline_scene": None,
            "achieved": False,
        }
        self.created.append(record)
        return record

    def list_anchors(self, *, root_id: str, branch_id: str) -> list[dict[str, object]]:
        self.list_anchors_called = (root_id, branch_id)
        return list(self.anchors)


class AnchorStub:
    def __init__(
        self,
        *,
        anchor_id: str,
        required_conditions: str,
        achieved: bool = False,
    ) -> None:
        self.id = anchor_id
        self.root_id = "root-alpha"
        self.branch_id = "branch-1"
        self.sequence = 1
        self.anchor_type = "inciting_incident"
        self.description = "anchor"
        self.constraint_type = "hard"
        self.required_conditions = required_conditions
        self.deadline_scene = None
        self.achieved = achieved


class ReachabilityStorage:
    def __init__(self, anchor: AnchorStub | None) -> None:
        self.anchor = anchor
        self.marked: tuple[str, str] | None = None

    def get_anchor(self, anchor_id: str):
        if self.anchor and self.anchor.id == anchor_id:
            return self.anchor
        return None

    def mark_anchor_achieved(
        self, *, anchor_id: str, scene_version_id: str
    ) -> dict[str, object]:
        self.marked = (anchor_id, scene_version_id)
        return {
            "id": anchor_id,
            "achieved": True,
        }


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_generate_anchors_creates_bulk(client):
    storage = AnchorStorage()
    anchors = _build_anchor_list()
    engine = SimpleNamespace(generate_story_anchors=AsyncMock(return_value=anchors))
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "branch_id": "branch-1",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/roots/root-alpha/anchors", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(anchors)
    assert storage.list_acts_called == "root-alpha"
    assert storage.created[0]["sequence"] == 1
    assert storage.created[-1]["sequence"] == len(anchors)
    created_types = {item["anchor_type"] for item in storage.created}
    for anchor_type in REQUIRED_ANCHOR_TYPES:
        assert anchor_type in created_types

    engine.generate_story_anchors.assert_awaited_once()
    args = engine.generate_story_anchors.await_args.args
    assert args[0].logline == payload["root"]["logline"]
    assert len(args[2]) == len(storage.acts)


def test_generate_anchors_rejects_invalid_count(client):
    storage = AnchorStorage()
    anchors = _build_anchor_list(count=9)
    engine = SimpleNamespace(generate_story_anchors=AsyncMock(return_value=anchors))
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "branch_id": "branch-1",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/roots/root-alpha/anchors", json=payload)

    assert response.status_code == 400
    assert storage.created == []


def test_generate_anchors_rejects_missing_fields(client):
    storage = AnchorStorage()
    anchors = _build_anchor_list()
    anchors[0].pop("description")
    engine = SimpleNamespace(generate_story_anchors=AsyncMock(return_value=anchors))
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "branch_id": "branch-1",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/roots/root-alpha/anchors", json=payload)

    assert response.status_code == 400
    assert storage.created == []


def test_list_anchors_returns_full_list(client):
    storage = AnchorStorage()
    storage.anchors = [
        {"id": "root-alpha:anchor:1", "achieved": False},
        {"id": "root-alpha:anchor:2", "achieved": True},
    ]
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get(
        "/api/v1/roots/root-alpha/anchors",
        params={"branch_id": "branch-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == ["root-alpha:anchor:1", "root-alpha:anchor:2"]
    assert storage.list_anchors_called == ("root-alpha", "branch-1")


def test_check_anchor_reachable_marks_achieved(client):
    anchor = AnchorStub(
        anchor_id="root-alpha:anchor:1",
        required_conditions='["hero_has_sword"]',
    )
    storage = ReachabilityStorage(anchor)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.post(
        "/api/v1/anchors/root-alpha:anchor:1/check",
        json={
            "world_state": {"hero_has_sword": True},
            "scene_version_id": "scene-alpha",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is True
    assert data["missing_conditions"] == []
    assert data["achieved"] is True
    assert storage.marked == ("root-alpha:anchor:1", "scene-alpha")


def test_check_anchor_unreachable_returns_missing_conditions(client):
    anchor = AnchorStub(
        anchor_id="root-alpha:anchor:1",
        required_conditions='["hero_has_sword", "ally_trusts_hero"]',
    )
    storage = ReachabilityStorage(anchor)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.post(
        "/api/v1/anchors/root-alpha:anchor:1/check",
        json={"world_state": {"hero_has_sword": True}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is False
    assert data["missing_conditions"] == ["ally_trusts_hero"]
    assert data["achieved"] is False
    assert storage.marked is None

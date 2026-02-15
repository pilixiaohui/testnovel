from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _subplot_payload() -> dict[str, object]:
    return {
        "branch_id": "branch-1",
        "title": "subplot",
        "subplot_type": "mystery",
        "protagonist_id": "entity-1",
        "central_conflict": "conflict",
    }


def _build_subplot(status: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="subplot-1",
        root_id="root-alpha",
        branch_id="branch-1",
        title="subplot",
        subplot_type="mystery",
        protagonist_id="entity-1",
        central_conflict="conflict",
        status=status,
    )


def _get_value(item: object, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


class SubplotStorage:
    def __init__(self, subplot: SimpleNamespace | None = None) -> None:
        self.subplot = subplot
        self.created: object | None = None
        self.updated: list[object] = []

    def create_subplot(self, subplot: object):
        self.created = subplot
        return subplot

    def get_subplot(self, subplot_id: str):
        if self.subplot and self.subplot.id == subplot_id:
            return self.subplot
        return None

    def update_subplot(self, subplot: object):
        self.updated.append(subplot)
        return subplot


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_create_subplot_creates_dormant_subplot(client):
    storage = SubplotStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    payload = _subplot_payload()
    response = client.post("/api/v1/roots/root-alpha/subplots", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["root_id"] == "root-alpha"
    assert data["branch_id"] == payload["branch_id"]
    assert data["title"] == payload["title"]
    assert data["subplot_type"] == payload["subplot_type"]
    assert data["protagonist_id"] == payload["protagonist_id"]
    assert data["central_conflict"] == payload["central_conflict"]
    assert data["status"] == "dormant"

    assert storage.created is not None
    assert _get_value(storage.created, "root_id") == "root-alpha"
    assert _get_value(storage.created, "branch_id") == payload["branch_id"]


def test_activate_subplot_endpoint_sets_active(client):
    subplot = _build_subplot(status="dormant")
    storage = SubplotStorage(subplot=subplot)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.post("/api/v1/subplots/subplot-1/activate")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "subplot-1"
    assert data["status"] == "active"
    assert storage.updated
    assert storage.updated[-1].status == "active"


def test_resolve_subplot_endpoint_sets_resolved(client):
    subplot = _build_subplot(status="active")
    storage = SubplotStorage(subplot=subplot)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.post("/api/v1/subplots/subplot-1/resolve")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "subplot-1"
    assert data["status"] == "resolved"
    assert storage.updated
    assert storage.updated[-1].status == "resolved"

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.main import app


class ActsChaptersStorage:
    def __init__(self) -> None:
        self.list_acts_called: str | None = None
        self.list_chapters_called: str | None = None
        self.acts: list[dict[str, object]] = []
        self.chapters: dict[str, list[dict[str, object]]] = {}

    def list_acts(self, *, root_id: str):
        self.list_acts_called = root_id
        return list(self.acts)

    def list_chapters(self, *, act_id: str):
        self.list_chapters_called = act_id
        return list(self.chapters.get(act_id, []))


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_list_acts_returns_ordered_list(client):
    storage = ActsChaptersStorage()
    storage.acts = [
        {
            "id": "root-alpha:act:1",
            "root_id": "root-alpha",
            "sequence": 1,
            "title": "Act 1",
            "purpose": "setup",
            "tone": "calm",
        },
        {
            "id": "root-alpha:act:2",
            "root_id": "root-alpha",
            "sequence": 2,
            "title": "Act 2",
            "purpose": "conflict",
            "tone": "tense",
        },
    ]
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/roots/root-alpha/acts")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == ["root-alpha:act:1", "root-alpha:act:2"]
    assert [item["sequence"] for item in data] == [1, 2]
    assert storage.list_acts_called == "root-alpha"


def test_list_acts_returns_empty_list(client):
    storage = ActsChaptersStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/roots/root-alpha/acts")

    assert response.status_code == 200
    assert response.json() == []
    assert storage.list_acts_called == "root-alpha"


def test_list_chapters_returns_ordered_list(client):
    storage = ActsChaptersStorage()
    storage.chapters["root-alpha:act:1"] = [
        {
            "id": "root-alpha:act:1:ch:1",
            "act_id": "root-alpha:act:1",
            "sequence": 1,
            "title": "Chapter 1",
            "focus": "opening",
            "pov_character_id": None,
        },
        {
            "id": "root-alpha:act:1:ch:2",
            "act_id": "root-alpha:act:1",
            "sequence": 2,
            "title": "Chapter 2",
            "focus": "escalation",
            "pov_character_id": "char-1",
        },
    ]
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/acts/root-alpha:act:1/chapters")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [
        "root-alpha:act:1:ch:1",
        "root-alpha:act:1:ch:2",
    ]
    assert [item["sequence"] for item in data] == [1, 2]
    assert storage.list_chapters_called == "root-alpha:act:1"


def test_list_chapters_returns_empty_list(client):
    storage = ActsChaptersStorage()
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/acts/root-alpha:act:2/chapters")

    assert response.status_code == 200
    assert response.json() == []
    assert storage.list_chapters_called == "root-alpha:act:2"

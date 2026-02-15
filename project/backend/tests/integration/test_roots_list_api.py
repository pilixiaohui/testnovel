from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _root_view(
    *,
    root_id: str,
    name: str,
    created_at: str,
    updated_at: str,
) -> dict[str, str]:
    return {
        "root_id": root_id,
        "name": name,
        "created_at": created_at,
        "updated_at": updated_at,
    }


class RootListStorage:
    def __init__(self, roots: list[dict[str, Any]]) -> None:
        self.roots = list(roots)
        self.last_call: tuple[int, int] | None = None

    def list_roots(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        self.last_call = (limit, offset)
        return self.roots[offset : offset + limit]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_list_roots_empty(client):
    storage = RootListStorage([])
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/roots", params={"limit": 20, "offset": 0})

    assert response.status_code == 200
    assert response.json() == {"roots": []}
    assert storage.last_call == (20, 0)


def test_list_roots_with_data(client):
    roots = [
        _root_view(
            root_id="root-2",
            name="Project Beta",
            created_at="2024-12-01T10:00:00Z",
            updated_at="2025-01-02T10:00:00Z",
        ),
        _root_view(
            root_id="root-alpha",
            name="Project Alpha",
            created_at="2024-11-01T10:00:00Z",
            updated_at="2025-01-01T10:00:00Z",
        ),
    ]
    storage = RootListStorage(roots)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/roots", params={"limit": 20, "offset": 0})

    assert response.status_code == 200
    data = response.json()
    assert data["roots"] == roots
    assert [item["root_id"] for item in data["roots"]] == ["root-2", "root-alpha"]
    assert storage.last_call == (20, 0)


def test_list_roots_pagination(client):
    roots = [
        _root_view(
            root_id="root-3",
            name="Project Gamma",
            created_at="2024-10-01T10:00:00Z",
            updated_at="2025-01-03T10:00:00Z",
        ),
        _root_view(
            root_id="root-2",
            name="Project Beta",
            created_at="2024-12-01T10:00:00Z",
            updated_at="2025-01-02T10:00:00Z",
        ),
        _root_view(
            root_id="root-alpha",
            name="Project Alpha",
            created_at="2024-11-01T10:00:00Z",
            updated_at="2025-01-01T10:00:00Z",
        ),
    ]
    storage = RootListStorage(roots)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage

    response = client.get("/api/v1/roots", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    data = response.json()
    assert data["roots"] == [roots[1]]
    assert storage.last_call == (1, 1)

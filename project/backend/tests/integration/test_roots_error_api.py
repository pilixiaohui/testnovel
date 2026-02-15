from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.main import app


class FailingListStorage:
    def list_roots(self, *, limit: int, offset: int) -> list[dict[str, str]]:
        raise RuntimeError("storage offline")


class FailingSaveStorage:
    def save_snowflake(self, root, characters, scenes) -> str:
        raise RuntimeError("storage offline")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_list_roots_returns_503_when_storage_unavailable(client):
    app.dependency_overrides[main.get_graph_storage] = lambda: FailingListStorage()

    response = client.get("/api/v1/roots", params={"limit": 20, "offset": 0})

    assert response.status_code == 503
    assert "storage unavailable" in response.json()["detail"]


def test_create_root_returns_503_when_storage_unavailable(client):
    app.dependency_overrides[main.get_graph_storage] = lambda: FailingSaveStorage()

    response = client.post("/api/v1/roots", json={"name": "示例项目"})

    assert response.status_code == 503
    assert "storage unavailable" in response.json()["detail"]

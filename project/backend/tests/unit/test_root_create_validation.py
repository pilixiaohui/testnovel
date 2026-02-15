from fastapi.testclient import TestClient
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_graph_storage


class DummyStorage:
    def save_snowflake(self, root, characters, scenes):
        return "root-created"


def test_create_project_rejects_malicious_name(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_graph_storage] = lambda: DummyStorage()

    client = TestClient(app)
    invalid_payloads = [
        {"name": "<script>alert(1)</script>"},
        {"name": "'; DROP TABLE roots; --"},
        {"name": "\u0000\uffff"},
    ]
    try:
        for payload in invalid_payloads:
            response = client.post("/api/v1/roots", json=payload)
            assert response.status_code == 422
            assert response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_create_project_rejects_invalid_name_types(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_graph_storage] = lambda: DummyStorage()

    client = TestClient(app)
    invalid_payloads = [
        {"name": 12345},
        {"name": None},
        {"name": True},
        {"name": "x" * 10000},
        {},
    ]
    try:
        for payload in invalid_payloads:
            response = client.post("/api/v1/roots", json=payload)
            assert response.status_code == 422
            assert response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


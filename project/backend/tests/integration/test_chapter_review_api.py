from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from tests.integration import storage_test_helpers as helpers


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def _seed_root(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = helpers.get_default_branch_id()
    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    helpers.seed_root_with_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        commit_id=commit_id,
    )
    return root_id, branch_id


def _seed_chapter(memgraph_storage) -> str:
    root_id, _branch_id = _seed_root(memgraph_storage)
    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    chapter = memgraph_storage.create_chapter(
        act_id=act["id"],
        seq=1,
        title="Chapter 1",
        focus="Focus",
        pov_character_id=None,
    )
    return chapter["id"]


def _override_storage(memgraph_storage) -> None:
    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage


def test_review_chapter_approved(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    _override_storage(memgraph_storage)

    response = client.post(
        f"/api/v1/chapters/{chapter_id}/review",
        json={"status": "approved"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == chapter_id
    assert payload["review_status"] == "approved"

    get_response = client.get(f"/api/v1/chapters/{chapter_id}")

    assert get_response.status_code == 200
    assert get_response.json()["review_status"] == "approved"


def test_review_chapter_rejected(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    _override_storage(memgraph_storage)

    response = client.post(
        f"/api/v1/chapters/{chapter_id}/review",
        json={"status": "rejected"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == chapter_id
    assert payload["review_status"] == "rejected"

    get_response = client.get(f"/api/v1/chapters/{chapter_id}")

    assert get_response.status_code == 200
    assert get_response.json()["review_status"] == "rejected"


def test_review_chapter_invalid_status(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    _override_storage(memgraph_storage)

    response = client.post(
        f"/api/v1/chapters/{chapter_id}/review",
        json={"status": "invalid_value"},
    )

    assert response.status_code == 400


def test_review_chapter_not_found(memgraph_storage, client):
    _override_storage(memgraph_storage)

    response = client.post(
        "/api/v1/chapters/nonexistent-uuid/review",
        json={"status": "approved"},
    )

    assert response.status_code == 404


def test_review_chapter_idempotent(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    _override_storage(memgraph_storage)

    response_one = client.post(
        f"/api/v1/chapters/{chapter_id}/review",
        json={"status": "approved"},
    )
    response_two = client.post(
        f"/api/v1/chapters/{chapter_id}/review",
        json={"status": "approved"},
    )

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert response_two.json()["review_status"] == "approved"

    get_response = client.get(f"/api/v1/chapters/{chapter_id}")

    assert get_response.status_code == 200
    assert get_response.json()["review_status"] == "approved"

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from tests.integration import storage_test_helpers as helpers

CHAPTER_COUNT = 10


@pytest.fixture()
def client(monkeypatch, memgraph_storage):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def _seed_chapters(memgraph_storage) -> list[str]:
    root_id = f"root-{uuid4()}"
    branch_id = helpers.get_default_branch_id()
    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    helpers.seed_root_with_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        commit_id=commit_id,
    )
    act = memgraph_storage.create_act(
        root_id=root_id,
        seq=1,
        title="Act 1",
        purpose="purpose",
        tone="calm",
    )
    chapter_ids: list[str] = []
    for idx in range(1, CHAPTER_COUNT + 1):
        chapter = memgraph_storage.create_chapter(
            act_id=act["id"],
            seq=idx,
            title=f"Chapter {idx}",
            focus="Focus",
            pov_character_id=None,
        )
        chapter_ids.append(chapter["id"])
    return chapter_ids


def test_review_e2e_flow(client, memgraph_storage):
    chapter_ids = _seed_chapters(memgraph_storage)
    assert len(chapter_ids) == CHAPTER_COUNT

    for chapter_id in chapter_ids:
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

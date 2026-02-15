from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from tests.integration import storage_test_helpers as helpers


class SequenceGateway:
    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)

    async def render_scene(self, payload):
        if not self._contents:
            return ""
        return self._contents.pop(0)


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


def _seed_chapter(memgraph_storage):
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


def test_unrendered_chapter_has_empty_rendered_content(memgraph_storage):
    chapter_id = _seed_chapter(memgraph_storage)

    chapter = memgraph_storage.get_chapter(chapter_id)

    assert chapter is not None
    assert chapter.rendered_content in (None, "")


def test_render_persists_rendered_content(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    gateway = SequenceGateway(["x" * 1900])

    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage
    app.dependency_overrides[main.get_topone_gateway] = lambda: gateway

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 200
    payload = response.json()
    assert 1800 <= len(payload["rendered_content"]) <= 2200

    chapter = memgraph_storage.get_chapter(chapter_id)
    assert chapter is not None
    assert chapter.rendered_content == payload["rendered_content"]


def test_render_updates_content_on_second_call(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    gateway = SequenceGateway(["a" * 1900, "b" * 1900])

    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage
    app.dependency_overrides[main.get_topone_gateway] = lambda: gateway

    response_one = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})
    response_two = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response_one.status_code == 200
    assert response_two.status_code == 200

    chapter = memgraph_storage.get_chapter(chapter_id)
    assert chapter is not None
    assert chapter.rendered_content == response_two.json()["rendered_content"]


def test_get_chapter_returns_rendered_content(memgraph_storage, client):
    chapter_id = _seed_chapter(memgraph_storage)
    gateway = SequenceGateway(["c" * 1900])

    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage
    app.dependency_overrides[main.get_topone_gateway] = lambda: gateway

    client.post(f"/api/v1/chapters/{chapter_id}/render", json={})
    response = client.get(f"/api/v1/chapters/{chapter_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("rendered_content") is not None

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import Chapter


class FlexibleRenderer:
    def __init__(self, content: str, error: Exception | None = None) -> None:
        self._content = content
        self._error = error

    def __getattr__(self, _name: str):
        async def _method(*_args: Any, **_kwargs: Any):
            if self._error:
                raise self._error
            return self._content

        return _method


class DummyStorage:
    def __init__(self, chapter: Chapter | None) -> None:
        self._chapter = chapter
        self.saved: list[tuple[str, str]] = []

    def get_chapter(self, chapter_id: str) -> Chapter | None:
        if self._chapter and self._chapter.id == chapter_id:
            return self._chapter
        return None

    def update_chapter(self, chapter: Chapter) -> Chapter:
        self._chapter = chapter
        return chapter

    def save_chapter_render(self, *, chapter_id: str, content: str) -> None:
        self.saved.append((chapter_id, content))


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def _build_chapter(chapter_id: str) -> Chapter:
    return Chapter(
        id=chapter_id,
        act_id="act-1",
        sequence=1,
        title="Chapter 1",
        focus="Focus",
        pov_character_id=None,
        rendered_content=None,
        review_status="pending",
    )


def _make_content(length: int) -> str:
    return "a" * length


def test_chapter_render_success_returns_content_and_word_count(client):
    chapter_id = "act-1:ch:1"
    storage = DummyStorage(_build_chapter(chapter_id))
    content = _make_content(1900)

    renderer = FlexibleRenderer(content)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 200
    payload = response.json()
    assert "rendered_content" in payload
    assert 1800 <= len(payload["rendered_content"]) <= 2200


def test_chapter_render_too_short_returns_400(client):
    chapter_id = "act-1:ch:1"
    storage = DummyStorage(_build_chapter(chapter_id))
    renderer = FlexibleRenderer(_make_content(1799))

    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "字数不足" in detail
    assert "1799" in detail
    assert "1800-2200" in detail
    assert "不含标点空白" in detail


def test_chapter_render_too_long_returns_400(client):
    chapter_id = "act-1:ch:1"
    storage = DummyStorage(_build_chapter(chapter_id))
    renderer = FlexibleRenderer(_make_content(2201))

    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "字数超限" in detail
    assert "2201" in detail
    assert "1800-2200" in detail
    assert "不含标点空白" in detail


def test_chapter_render_ignores_punctuation_and_whitespace_when_counting(client):
    chapter_id = "act-1:ch:1"
    storage = DummyStorage(_build_chapter(chapter_id))
    base = _make_content(1800)
    extra = " ,.!?" * 100
    content = base + extra

    assert len(content) > 2200

    renderer = FlexibleRenderer(content)
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 200


def test_chapter_render_missing_chapter_returns_404(client):
    storage = DummyStorage(None)
    renderer = FlexibleRenderer(_make_content(1900))
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post("/api/v1/chapters/missing/render", json={})

    assert response.status_code == 404


def test_chapter_render_failure_returns_400(client):
    chapter_id = "act-1:ch:1"
    storage = DummyStorage(_build_chapter(chapter_id))
    renderer = FlexibleRenderer("", error=ValueError("render failed"))

    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: renderer
    app.dependency_overrides[main.get_smart_renderer] = lambda: renderer
    app.dependency_overrides[main.get_topone_gateway] = lambda: renderer

    response = client.post(f"/api/v1/chapters/{chapter_id}/render", json={})

    assert response.status_code == 400

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app, get_graph_storage, get_llm_engine


class DummyEngine:
    def __init__(self, counts_by_act: dict[str, int]) -> None:
        self._counts_by_act = counts_by_act

    async def generate_chapter_list(self, root, act, characters):
        count = self._counts_by_act.get(act.get("id"), 0)
        return [
            {
                "title": f"Chapter {idx + 1}",
                "focus": f"Focus {idx + 1}",
                "pov_character_id": None,
            }
            for idx in range(count)
        ]


class DummyStorage:
    def __init__(self, acts: list[dict]) -> None:
        self._acts = acts
        self.created: list[dict] = []

    def list_acts(self, *, root_id: str):
        return self._acts

    def create_chapter(
        self,
        *,
        act_id: str,
        seq: int,
        title: str,
        focus: str,
        pov_character_id: str | None = None,
        rendered_content: str | None = None,
        review_status: str = "pending",
    ) -> dict:
        chapter = {
            "id": f"{act_id}:ch:{seq}",
            "act_id": act_id,
            "sequence": seq,
            "title": title,
            "focus": focus,
            "pov_character_id": pov_character_id,
            "rendered_content": rendered_content,
            "review_status": review_status,
        }
        self.created.append(chapter)
        return chapter


def _payload() -> dict:
    return {
        "root_id": "root-alpha",
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Theme",
        },
        "characters": [],
    }


def _call_step5b(monkeypatch, counts_by_act: dict[str, int], acts: list[dict]):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    engine = DummyEngine(counts_by_act)
    storage = DummyStorage(acts)

    app.dependency_overrides[get_llm_engine] = lambda: engine
    app.dependency_overrides[get_graph_storage] = lambda: storage
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/snowflake/step5b", json=_payload())
    finally:
        app.dependency_overrides.clear()
    return response, storage


def test_step5b_returns_10_chapters_when_total_is_10(monkeypatch):
    acts = [{"id": "act-1"}, {"id": "act-2"}]
    response, storage = _call_step5b(
        monkeypatch,
        {"act-1": 5, "act-2": 5},
        acts,
    )

    assert response.status_code == 200
    assert len(response.json()) == 10
    assert len(storage.created) == 10


def test_step5b_returns_422_when_total_less_than_10(monkeypatch):
    acts = [{"id": "act-1"}]
    response, _ = _call_step5b(monkeypatch, {"act-1": 9}, acts)

    assert response.status_code == 422


def test_step5b_returns_422_when_total_greater_than_10(monkeypatch):
    acts = [{"id": "act-1"}]
    response, _ = _call_step5b(monkeypatch, {"act-1": 11}, acts)

    assert response.status_code == 422

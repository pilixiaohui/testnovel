from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _root_payload() -> dict[str, object]:
    return {
        "logline": "A hero seeks redemption.",
        "three_disasters": ["loss", "betrayal", "reckoning"],
        "ending": "peace",
        "theme": "forgiveness",
    }


def _character_payload() -> dict[str, object]:
    return {
        "name": "Hero",
        "ambition": "redeem",
        "conflict": "guilt",
        "epiphany": "forgive",
        "voice_dna": "steady",
    }


class Step5Storage:
    def __init__(self) -> None:
        self.created_acts: list[dict[str, object]] = []
        self.created_chapters: list[dict[str, object]] = []
        self.acts: list[dict[str, object]] = [{"id": "act-1"}]

    def create_act(self, *, root_id: str, seq: int, title: str, purpose: str, tone: str):
        record = {
            "id": f"{root_id}:act:{seq}",
            "root_id": root_id,
            "sequence": seq,
            "title": title,
            "purpose": purpose,
            "tone": tone,
        }
        self.created_acts.append(record)
        return record

    def list_acts(self, *, root_id: str):
        _ = root_id
        return list(self.acts)

    def create_chapter(
        self,
        *,
        act_id: str,
        seq: int,
        title: str,
        focus: str,
        pov_character_id: str | None = None,
    ):
        record = {
            "id": f"{act_id}:ch:{seq}",
            "act_id": act_id,
            "sequence": seq,
            "title": title,
            "focus": focus,
            "pov_character_id": pov_character_id,
        }
        self.created_chapters.append(record)
        return record


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_step5a_generates_acts(client):
    storage = Step5Storage()
    engine = SimpleNamespace(
        generate_act_list=AsyncMock(
            return_value=[{"title": "Act 1", "purpose": "setup", "tone": "calm"}]
        )
    )
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "root_id": "root-alpha",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/snowflake/step5a", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data[0]["title"] == "Act 1"
    assert storage.created_acts[0]["sequence"] == 1
    engine.generate_act_list.assert_awaited_once()


def test_step5b_generates_chapters(client):
    storage = Step5Storage()
    engine = SimpleNamespace(
        generate_chapter_list=AsyncMock(
            return_value=[
                {
                    "title": f"Chapter {idx}",
                    "focus": f"focus {idx}",
                    "pov_character_id": None,
                }
                for idx in range(1, 11)
            ]
        )
    )
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine

    payload = {
        "root_id": "root-alpha",
        "root": _root_payload(),
        "characters": [_character_payload()],
    }
    response = client.post("/api/v1/snowflake/step5b", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data[0]["act_id"] == "act-1"
    assert storage.created_chapters[0]["sequence"] == 1
    engine.generate_chapter_list.assert_awaited_once()

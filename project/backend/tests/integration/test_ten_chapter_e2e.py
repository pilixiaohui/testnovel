from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import SCENE_MAX_COUNT, SCENE_MIN_COUNT
from app.constants import DEFAULT_BRANCH_ID
from app.logic.snowflake_manager import SnowflakeManager
from app.main import app
from app.models import (
    CharacterSheet,
    CharacterValidationResult,
    SceneNode,
    SnowflakeRoot,
)

STORY_IDEA = "名为何方的时空旅人穿越到赛博朋克世界的日常生活故事"
RENDERED_CONTENT = "a" * 2000
CHAPTER_COUNT = 10


class FakeEngine:
    async def generate_logline_options(self, raw_idea: str) -> list[str]:
        return [f"{raw_idea}-logline-{idx}" for idx in range(1, 11)]

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:
        return SnowflakeRoot(
            logline=idea,
            three_disasters=["loss", "betrayal", "reckoning"],
            ending="peace",
            theme="identity",
        )

    async def generate_characters(self, _root: SnowflakeRoot) -> list[CharacterSheet]:
        return [
            CharacterSheet(
                name="Traveler",
                ambition="find home",
                conflict="temporal drift",
                epiphany="accept change",
                voice_dna="quiet",
            ),
            CharacterSheet(
                name="Cipher",
                ambition="protect community",
                conflict="corporate pressure",
                epiphany="trust allies",
                voice_dna="sharp",
            ),
        ]

    async def validate_characters(
        self, _root: SnowflakeRoot, _characters: list[CharacterSheet]
    ) -> CharacterValidationResult:
        return CharacterValidationResult(valid=True, issues=[])

    async def generate_scene_list(
        self, _root: SnowflakeRoot, _characters: list[CharacterSheet]
    ) -> list[SceneNode]:
        scenes: list[SceneNode] = []
        for idx in range(SCENE_MIN_COUNT):
            scenes.append(
                SceneNode(
                    branch_id=DEFAULT_BRANCH_ID,
                    title=f"Scene {idx + 1}",
                    sequence_index=idx,
                    parent_act_id=None,
                    pov_character_id=None,
                    expected_outcome="progress",
                    conflict_type="internal",
                    actual_outcome="unknown",
                    is_dirty=False,
                )
            )
        return scenes

    async def generate_act_list(self, _root: SnowflakeRoot, _characters: list[CharacterSheet]):
        return [{"title": "Act 1", "purpose": "setup", "tone": "calm"}]

    async def generate_chapter_list(
        self, _root: SnowflakeRoot, _act: dict[str, object], _characters: list[CharacterSheet]
    ) -> list[dict[str, object]]:
        return [
            {
                "title": f"Chapter {idx + 1}",
                "focus": f"Focus {idx + 1}",
                "pov_character_id": None,
            }
            for idx in range(CHAPTER_COUNT)
        ]

    async def generate_story_anchors(
        self,
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
        _acts: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return [
            {
                "anchor_type": "inciting_incident",
                "description": f"Anchor {idx + 1}",
                "constraint_type": "soft",
                "required_conditions": [],
            }
            for idx in range(CHAPTER_COUNT)
        ]


class FakeGateway:
    async def render_scene(self, _payload):
        return RENDERED_CONTENT


@pytest.fixture()
def client(monkeypatch, memgraph_storage):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    engine = FakeEngine()
    manager = SnowflakeManager(
        engine=engine,
        storage=memgraph_storage,
        min_scenes=SCENE_MIN_COUNT,
        max_scenes=SCENE_MAX_COUNT,
    )
    app.dependency_overrides = {}
    app.dependency_overrides[main.get_graph_storage] = lambda: memgraph_storage
    app.dependency_overrides[main.get_llm_engine] = lambda: engine
    app.dependency_overrides[main.get_snowflake_manager] = lambda: manager
    app.dependency_overrides[main.get_topone_gateway] = lambda: FakeGateway()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_ten_chapter_e2e_flow(client):
    response = client.post("/api/v1/snowflake/step1", json={"idea": STORY_IDEA})
    assert response.status_code == 200
    loglines = response.json()
    assert len(loglines) == 10

    response = client.post("/api/v1/snowflake/step2", json={"logline": loglines[0]})
    assert response.status_code == 200
    root = response.json()

    response = client.post("/api/v1/snowflake/step3", json=root)
    assert response.status_code == 200
    characters = response.json()
    assert len(characters) >= 1

    response = client.post(
        "/api/v1/snowflake/step4",
        json={"root": root, "characters": characters},
    )
    assert response.status_code == 200
    step4 = response.json()
    root_id = step4["root_id"]
    branch_id = step4["branch_id"]
    assert len(step4["scenes"]) == SCENE_MIN_COUNT

    step5_payload = {"root_id": root_id, "root": root, "characters": characters}
    response = client.post("/api/v1/snowflake/step5a", json=step5_payload)
    assert response.status_code == 200
    acts = response.json()
    assert len(acts) == 1

    response = client.post("/api/v1/snowflake/step5b", json=step5_payload)
    assert response.status_code == 200
    chapters = response.json()
    assert len(chapters) == CHAPTER_COUNT

    response = client.post(
        f"/api/v1/roots/{root_id}/anchors",
        json={
            "branch_id": branch_id,
            "root": root,
            "characters": characters,
        },
    )
    assert response.status_code == 200
    anchors = response.json()
    assert len(anchors) == CHAPTER_COUNT

    for chapter in chapters:
        render_response = client.post(
            f"/api/v1/chapters/{chapter['id']}/render",
            json={},
        )
        assert render_response.status_code == 200
        payload = render_response.json()
        content = payload.get("rendered_content")
        assert content
        assert 1800 <= len(content) <= 2200

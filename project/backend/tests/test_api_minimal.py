import httpx
import pytest
from fastapi.testclient import TestClient

from app.constants import DEFAULT_BRANCH_ID
from app.llm.schemas import ImpactLevel, LogicCheckResult, StateProposal
from app.main import (
    app,
    get_graph_storage,
    get_llm_engine,
    get_snowflake_manager,
    get_topone_client,
    get_topone_gateway,
)
from app.models import SceneNode, SnowflakeRoot


class DummyEngine:
    async def generate_root_structure(self, logline: str) -> SnowflakeRoot:
        return SnowflakeRoot(
            logline="Test story",
            three_disasters=["D1", "D2", "D3"],
            ending="End",
            theme="Testing",
        )


class InvalidOutputEngine:
    async def generate_root_structure(self, logline: str) -> SnowflakeRoot:
        raise ValueError("invalid JSON from model output")

    async def generate_characters(self, root: SnowflakeRoot):
        raise ValueError("invalid JSON from model output")


class RateLimitedEngine:
    async def generate_root_structure(self, logline: str) -> SnowflakeRoot:
        request = httpx.Request("POST", "https://api.test/llm")
        response = httpx.Response(status_code=429, request=request)
        raise httpx.HTTPStatusError("rate limit", request=request, response=response)


class MalformedStep5Engine:
    async def generate_act_list(self, root: SnowflakeRoot, characters):
        return ["malformed"]

    async def generate_chapter_list(self, root: SnowflakeRoot, act, characters):
        return ["malformed"] * 8


class DummyStep5Storage:
    def __init__(self) -> None:
        self.acts = [{"id": "act-alpha"}]

    def create_act(self, *, root_id: str, seq: int, title: str, purpose: str, tone: str) -> dict[str, object]:
        return {
            "id": f"{root_id}:act:{seq}",
            "root_id": root_id,
            "sequence": seq,
            "title": title,
            "purpose": purpose,
            "tone": tone,
        }

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
        pov_character_id: str | None,
    ) -> dict[str, object]:
        return {
            "id": f"{act_id}:chapter:{seq}",
            "act_id": act_id,
            "sequence": seq,
            "title": title,
            "focus": focus,
            "pov_character_id": pov_character_id,
        }


class DummyManager:
    def __init__(self) -> None:
        self.last_persisted_root_id = "root-alpha"

    async def execute_step_1_logline(self, idea: str) -> list[str]:
        return [f"logline:{idea}"]

    async def execute_step_4_scenes(self, root: SnowflakeRoot, characters):
        return [
            SceneNode(
                branch_id=DEFAULT_BRANCH_ID,
                title="Scene 1",
                sequence_index=0,
                expected_outcome="Outcome 1",
                conflict_type="internal",
                actual_outcome="",
                parent_act_id=None,
                is_dirty=False,
            )
        ]


class InvalidOutputManager:
    def __init__(self) -> None:
        self.last_persisted_root_id = ""

    async def execute_step_1_logline(self, idea: str) -> list[str]:
        raise ValueError("invalid JSON from model output")

    async def execute_step_4_scenes(self, root: SnowflakeRoot, characters):
        raise ValueError("invalid JSON from model output")


class DummyToponeClient:
    async def generate_content(self, **kwargs):
        return {"ok": True}


class DummyGateway:
    async def state_extract(self, payload):
        return [
            StateProposal(
                entity_id="entity-1",
                confidence=0.9,
                semantic_states_patch={"hp": "90%"},
            )
        ]

    async def logic_check(self, payload):
        return LogicCheckResult(
            ok=True,
            mode=payload.mode,
            decision="execute",
            impact_level=ImpactLevel.LOCAL,
            warnings=[],
        )

    async def render_scene(self, payload):
        return "Rendered text"


class DummyStorage:
    def __init__(self) -> None:
        self.states: dict[str, dict] = {}
        self.dirty: set[str] = set()
        self.required: list[tuple[str, str]] = []
        self.branches: set[str] = {DEFAULT_BRANCH_ID}
        self.entity_counter = 0
        self.entities: dict[str, dict] = {}
        self.rendered: dict[str, str] = {}
        self.completed: dict[str, dict] = {}
        self.logic_exceptions: dict[tuple[str, str, str], str] = {}
        self.logic_world_state_calls: list[tuple[str, str, str]] = []
        self.local_fixes: list[tuple[str, str, str, int]] = []
        self.future_dirty_calls: list[tuple[str, str, str]] = []
        self.created_project_name: str | None = None
        self.deleted_root_id: str | None = None

    def require_root(self, *, root_id: str, branch_id: str) -> None:
        self.required.append((root_id, branch_id))

    def get_entity_semantic_states(
        self, *, root_id: str, branch_id: str, entity_id: str
    ) -> dict:
        return self.states.get(entity_id, {}).copy()

    def build_logic_check_world_state(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> dict:
        self.logic_world_state_calls.append((root_id, branch_id, scene_id))
        return {"root_id": root_id, "branch_id": branch_id, "scene_id": scene_id}

    def mark_scene_logic_exception(
        self, *, root_id: str, branch_id: str, scene_id: str, reason: str
    ) -> None:
        self.logic_exceptions[(root_id, branch_id, scene_id)] = reason

    def is_scene_logic_exception(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> bool:
        return (root_id, branch_id, scene_id) in self.logic_exceptions

    def apply_local_scene_fix(
        self, *, root_id: str, branch_id: str, scene_id: str, limit: int = 3
    ) -> list[str]:
        self.local_fixes.append((root_id, branch_id, scene_id, limit))
        return [scene_id]

    def mark_future_scenes_dirty(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> list[str]:
        self.future_dirty_calls.append((root_id, branch_id, scene_id))
        return [scene_id]

    def apply_semantic_states_patch(
        self, *, root_id: str, branch_id: str, entity_id: str, patch: dict
    ) -> dict:
        current = self.states.get(entity_id, {})
        updated = {**current, **patch}
        self.states[entity_id] = updated
        return updated

    def mark_scene_dirty(self, *, scene_id: str, branch_id: str) -> None:
        self.dirty.add(scene_id)

    def list_dirty_scenes(self, *, root_id: str, branch_id: str) -> list[str]:
        return sorted(self.dirty)

    def create_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id in self.branches:
            raise ValueError("already exists")
        self.branches.add(branch_id)

    def list_branches(self, *, root_id: str) -> list[str]:
        return sorted(self.branches)

    def require_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def merge_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def revert_branch(self, *, root_id: str, branch_id: str) -> None:
        if branch_id not in self.branches:
            raise KeyError(f"branch not found: {branch_id}")

    def fork_from_commit(
        self,
        *,
        root_id: str,
        source_commit_id: str,
        new_branch_id: str,
        parent_branch_id: str | None = None,
        fork_scene_origin_id: str | None = None,
    ) -> None:
        self.branches.add(new_branch_id)

    def fork_from_scene(
        self,
        *,
        root_id: str,
        source_branch_id: str,
        scene_origin_id: str,
        new_branch_id: str,
        commit_id: str | None = None,
    ) -> None:
        self.branches.add(new_branch_id)

    def reset_branch_head(
        self, *, root_id: str, branch_id: str, commit_id: str
    ) -> None:
        return

    def get_branch_history(
        self, *, root_id: str, branch_id: str, limit: int = 50
    ) -> list[dict]:
        return [
            {
                "id": "commit-1",
                "parent_id": None,
                "root_id": root_id,
                "created_at": "2025-01-01T00:00:00Z",
                "message": "commit",
            }
        ]

    def get_root_snapshot(self, *, root_id: str, branch_id: str) -> dict:
        return {
            "root_id": root_id,
            "branch_id": branch_id,
            "logline": "logline",
            "theme": "theme",
            "ending": "ending",
            "characters": [],
            "scenes": [],
            "relations": [],
        }

    def create_entity(
        self,
        *,
        root_id: str,
        branch_id: str,
        name: str,
        entity_type: str,
        tags: list[str],
        arc_status: str | None,
        semantic_states: dict,
    ) -> str:
        self.entity_counter += 1
        entity_id = f"entity-{self.entity_counter}"
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "name": name,
            "entity_type": entity_type,
            "tags": tags,
            "arc_status": arc_status,
            "semantic_states": semantic_states,
        }
        return entity_id

    def list_entities(self, *, root_id: str, branch_id: str) -> list[dict]:
        return list(self.entities.values())

    def upsert_entity_relation(
        self,
        *,
        root_id: str,
        branch_id: str,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        tension: int,
    ) -> None:
        return

    def get_scene_context(self, *, scene_id: str, branch_id: str) -> dict:
        return {
            "root_id": "root",
            "branch_id": branch_id,
            "expected_outcome": "Outcome 1",
            "semantic_states": {},
            "summary": "Summary 1",
            "scene_entities": [],
            "characters": [],
            "relations": [],
            "prev_scene_id": None,
            "next_scene_id": None,
        }

    def diff_scene_versions(
        self, *, scene_origin_id: str, from_commit_id: str, to_commit_id: str
    ) -> dict:
        return {"actual_outcome": {"from": "", "to": "updated"}}

    def commit_scene(
        self,
        *,
        root_id: str,
        branch_id: str,
        scene_origin_id: str,
        content: dict,
        message: str,
        expected_head_version: int | None = None,
    ) -> dict:
        return {"commit_id": "commit-1", "scene_version_ids": ["version-1"]}

    def create_scene_origin(
        self,
        *,
        root_id: str,
        branch_id: str,
        title: str,
        parent_act_id: str,
        content: dict,
    ) -> dict:
        return {
            "commit_id": "commit-1",
            "scene_origin_id": "origin-1",
            "scene_version_id": "version-1",
        }

    def delete_scene_origin(
        self, *, root_id: str, branch_id: str, scene_origin_id: str, message: str
    ) -> dict:
        return {"commit_id": "commit-2", "scene_version_ids": []}

    def gc_orphan_commits(self, *, retention_days: int) -> dict:
        return {
            "deleted_commit_ids": ["commit-1"],
            "deleted_scene_version_ids": ["version-1"],
        }

    def save_snowflake(self, root, characters, scenes) -> str:
        self.created_project_name = root.logline
        return "root-created"

    def delete_root(self, root_id: str) -> None:
        self.deleted_root_id = root_id

    def save_scene_render(self, *, scene_id: str, branch_id: str, content: str) -> None:
        self.rendered[scene_id] = content

    def complete_scene(
        self, *, scene_id: str, branch_id: str, actual_outcome: str, summary: str
    ) -> None:
        self.completed[scene_id] = {
            "actual_outcome": actual_outcome,
            "summary": summary,
        }


def test_step2_generate_structure_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: DummyEngine()

    client = TestClient(app)
    try:
        response = client.post("/api/v1/snowflake/step2", json={"logline": "raw idea"})
        assert response.status_code == 200
        data = response.json()
        assert data["logline"] == "Test story"
        assert len(data["three_disasters"]) == 3
    finally:
        app.dependency_overrides.clear()


def test_step1_generate_loglines_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_snowflake_manager] = lambda: DummyManager()

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/snowflake/step1", json={"idea": "seed"}
        )
        assert response.status_code == 200
        assert response.json() == ["logline:seed"]
    finally:
        app.dependency_overrides.clear()


def test_step4_generate_scene_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_snowflake_manager] = lambda: DummyManager()

    client = TestClient(app)
    payload = {
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Testing",
        },
        "characters": [
            {
                "name": "Hero",
                "ambition": "A",
                "conflict": "B",
                "epiphany": "C",
                "voice_dna": "D",
            }
        ],
    }
    try:
        response = client.post("/api/v1/snowflake/step4", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["root_id"] == "root-alpha"
        assert data["branch_id"] == DEFAULT_BRANCH_ID
        assert data["scenes"][0]["expected_outcome"] == "Outcome 1"
    finally:
        app.dependency_overrides.clear()


def test_step2_returns_422_when_engine_output_invalid(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: InvalidOutputEngine()

    client = TestClient(app)
    try:
        response = client.post("/api/v1/snowflake/step2", json={"logline": "raw idea"})
        assert response.status_code == 422
        assert "invalid JSON" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_step2_returns_upstream_status_when_engine_rate_limited(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: RateLimitedEngine()

    client = TestClient(app)
    try:
        response = client.post("/api/v1/snowflake/step2", json={"logline": "raw idea"})
        assert response.status_code == 429
    finally:
        app.dependency_overrides.clear()


def test_step3_returns_422_when_engine_output_invalid(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: InvalidOutputEngine()

    client = TestClient(app)
    payload = {
        "logline": "Test story",
        "three_disasters": ["D1", "D2", "D3"],
        "ending": "End",
        "theme": "Testing",
    }
    try:
        response = client.post("/api/v1/snowflake/step3", json=payload)
        assert response.status_code == 422
        assert "invalid JSON" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_step4_returns_422_when_manager_output_invalid(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_snowflake_manager] = lambda: InvalidOutputManager()

    client = TestClient(app)
    payload = {
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Testing",
        },
        "characters": [
            {
                "name": "Hero",
                "ambition": "A",
                "conflict": "B",
                "epiphany": "C",
                "voice_dna": "D",
            }
        ],
    }
    try:
        response = client.post("/api/v1/snowflake/step4", json=payload)
        assert response.status_code == 422
        assert "invalid JSON" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()



def test_step5a_returns_422_when_engine_returns_non_object_act(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: MalformedStep5Engine()
    app.dependency_overrides[get_graph_storage] = lambda: DummyStep5Storage()

    client = TestClient(app)
    payload = {
        "root_id": "root-alpha",
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Testing",
        },
        "characters": [
            {
                "name": "Hero",
                "ambition": "A",
                "conflict": "B",
                "epiphany": "C",
                "voice_dna": "D",
            }
        ],
    }
    try:
        response = client.post("/api/v1/snowflake/step5a", json=payload)
        assert response.status_code == 422
        assert "step5a act item must be object" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_step5b_returns_422_when_engine_returns_non_object_chapter(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_llm_engine] = lambda: MalformedStep5Engine()
    app.dependency_overrides[get_graph_storage] = lambda: DummyStep5Storage()

    client = TestClient(app)
    payload = {
        "root_id": "root-alpha",
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Testing",
        },
        "characters": [
            {
                "name": "Hero",
                "ambition": "A",
                "conflict": "B",
                "epiphany": "C",
                "voice_dna": "D",
            }
        ],
    }
    try:
        response = client.post("/api/v1/snowflake/step5b", json=payload)
        assert response.status_code == 422
        assert "step5b chapter item must be object" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_topone_generate_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_topone_client] = lambda: DummyToponeClient()

    client = TestClient(app)
    payload = {
        "model": "gemini-3-flash-preview",
        "system_instruction": "sys",
        "messages": [{"role": "user", "text": "hi"}],
        "generation_config": {"temperature": 0.5},
        "timeout": 600,
    }
    try:
        response = client.post("/api/v1/llm/topone/generate", json=payload)
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    finally:
        app.dependency_overrides.clear()


def test_topone_generate_rejects_timeout_less_than_600(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_topone_client] = lambda: DummyToponeClient()

    client = TestClient(app)
    payload = {
        "messages": [{"role": "user", "text": "hi"}],
        "timeout": 30,
    }
    try:
        response = client.post("/api/v1/llm/topone/generate", json=payload)
        assert response.status_code == 422
        assert any(
            "timeout" in error.get("loc", [])
            for error in response.json().get("detail", [])
        )
    finally:
        app.dependency_overrides.clear()


def test_create_project_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.post("/api/v1/roots", json={"name": "赛博穿越者项目"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["root_id"] == "root-created"
        assert payload["name"] == "赛博穿越者项目"
        assert payload["created_at"]
        assert payload["updated_at"]
        assert storage.created_project_name == "赛博穿越者项目"
    finally:
        app.dependency_overrides.clear()


def test_delete_project_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.delete("/api/v1/roots/root-created")
        assert response.status_code == 200
        assert response.json() == {"success": True}
        assert storage.deleted_root_id == "root-created"
    finally:
        app.dependency_overrides.clear()


def test_simulation_agents_endpoint_returns_empty_agents(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    client = TestClient(app)

    response = client.get(
        "/api/v1/simulation/agents",
        params={"root_id": "root-alpha", "branch_id": DEFAULT_BRANCH_ID},
    )

    assert response.status_code == 200
    assert response.json() == {"agents": [], "convergence": None}


def test_logic_check_rejects_non_gemini(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_graph_storage] = lambda: DummyStorage()
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    payload = {
        "outline_requirement": "outline",
        "world_state": {},
        "user_intent": "intent",
        "mode": "standard",
    }
    try:
        response = client.post("/api/v1/logic/check", json=payload)
        assert response.status_code == 400
        assert "gemini" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_state_extract_returns_gateway_result_without_root(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    app.dependency_overrides[get_graph_storage] = lambda: DummyStorage()
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    payload = {"content": "text", "entity_ids": ["entity-1"]}
    try:
        response = client.post("/api/v1/state/extract", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result[0]["entity_id"] == "entity-1"
        assert result[0]["semantic_states_patch"] == {"hp": "90%"}
    finally:
        app.dependency_overrides.clear()


def test_state_extract_local_mode_returns_basic_proposals(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    payload = {
        "content": "text",
        "entity_ids": ["entity-1"],
        "root_id": "root-alpha",
        "branch_id": DEFAULT_BRANCH_ID,
    }
    try:
        response = client.post("/api/v1/state/extract", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result[0]["entity_id"] == "entity-1"
        assert result[0]["semantic_states_patch"] == {}
        assert result[0]["semantic_states_before"] == {}
        assert result[0]["semantic_states_after"] == {}
    finally:
        app.dependency_overrides.clear()


def test_state_commit_applies_patch(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    payload = [
        {
            "entity_id": "entity-1",
            "confidence": 0.9,
            "semantic_states_patch": {"hp": "80%"},
        }
    ]
    try:
        response = client.post(
            "/api/v1/state/commit",
            params={"root_id": "root", "branch_id": "branch"},
            json=payload,
        )
        assert response.status_code == 200
        assert response.json()["applied"] == 1
        assert storage.states["entity-1"]["hp"] == "80%"
    finally:
        app.dependency_overrides.clear()


def test_dirty_endpoints_roundtrip(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/scenes/scene-alpha/dirty", params={"branch_id": DEFAULT_BRANCH_ID}
        )
        assert response.status_code == 200

        listing = client.get(
            "/api/v1/roots/root-alpha/dirty_scenes", params={"branch_id": DEFAULT_BRANCH_ID}
        )
        assert listing.status_code == 200
        assert listing.json() == ["scene-alpha"]
    finally:
        app.dependency_overrides.clear()


def test_branch_endpoints_roundtrip(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        listing = client.get("/api/v1/roots/root-alpha/branches")
        assert listing.status_code == 200
        assert listing.json() == [DEFAULT_BRANCH_ID]

        created = client.post(
            "/api/v1/roots/root-alpha/branches", json={"branch_id": "dev"}
        )
        assert created.status_code == 200
        assert created.json()["branch_id"] == "dev"

        listing = client.get("/api/v1/roots/root-alpha/branches")
        assert listing.status_code == 200
        assert set(listing.json()) == {DEFAULT_BRANCH_ID, "dev"}

        switched = client.post("/api/v1/roots/root-alpha/branches/dev/switch")
        assert switched.status_code == 200
        assert switched.json()["branch_id"] == "dev"
    finally:
        app.dependency_overrides.clear()


def test_root_graph_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/roots/root-alpha", params={"branch_id": DEFAULT_BRANCH_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["root_id"] == "root-alpha"
        assert data["branch_id"] == DEFAULT_BRANCH_ID
    finally:
        app.dependency_overrides.clear()


def test_entity_endpoints_roundtrip(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        payload = {
            "name": "Hero",
            "entity_type": "npc",
            "tags": ["a"],
            "arc_status": None,
            "semantic_states": {"hp": "100%"},
        }
        created = client.post(
            "/api/v1/roots/root-alpha/entities",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json=payload,
        )
        assert created.status_code == 200
        entity_id = created.json()["entity_id"]

        listing = client.get(
            "/api/v1/roots/root-alpha/entities",
            params={"branch_id": DEFAULT_BRANCH_ID},
        )
        assert listing.status_code == 200
        assert listing.json()[0]["entity_id"] == entity_id
    finally:
        app.dependency_overrides.clear()


def test_relation_upsert_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        payload = {
            "from_entity_id": "entity-a",
            "to_entity_id": "entity-b",
            "relation_type": "ally",
            "tension": 20,
        }
        response = client.post(
            "/api/v1/roots/root-alpha/relations",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json=payload,
        )
        assert response.status_code == 200
        assert response.json()["relation_type"] == "ally"
    finally:
        app.dependency_overrides.clear()


def test_scene_context_and_diff_endpoints(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        context = client.get(
            "/api/v1/scenes/scene-alpha/context",
            params={"branch_id": DEFAULT_BRANCH_ID},
        )
        assert context.status_code == 200
        assert context.json()["expected_outcome"] == "Outcome 1"

        diff = client.get(
            "/api/v1/scenes/scene-alpha/diff",
            params={"from_commit_id": "c1", "to_commit_id": "c2"},
        )
        assert diff.status_code == 200
        assert diff.json()["actual_outcome"]["to"] == "updated"
    finally:
        app.dependency_overrides.clear()


def test_commit_scene_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    payload = {
        "scene_origin_id": "scene-alpha",
        "content": {
            "actual_outcome": "Outcome A",
            "summary": "Summary A",
            "status": "committed",
        },
        "message": "commit A",
    }
    try:
        response = client.post(
            f"/api/v1/roots/root-alpha/branches/{DEFAULT_BRANCH_ID}/commit",
            json=payload,
        )
        assert response.status_code == 200
        assert response.json()["commit_id"] == "commit-1"
    finally:
        app.dependency_overrides.clear()


def test_create_and_delete_scene_origin_endpoints(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    create_payload = {
        "title": "New scene",
        "parent_act_id": "act-1",
        "content": {
            "pov_character_id": "entity-1",
            "expected_outcome": "Outcome X",
            "conflict_type": "internal",
            "actual_outcome": "",
        },
    }
    try:
        created = client.post(
            "/api/v1/roots/root-alpha/scene_origins",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json=create_payload,
        )
        assert created.status_code == 200
        scene_origin_id = created.json()["scene_origin_id"]

        deleted = client.post(
            f"/api/v1/roots/root-alpha/scenes/{scene_origin_id}/delete",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json={"message": "archive scene"},
        )
        assert deleted.status_code == 200
        assert deleted.json()["commit_id"] == "commit-2"
    finally:
        app.dependency_overrides.clear()


def test_gc_commits_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.post("/api/v1/commits/gc", json={"retention_days": 0})
        assert response.status_code == 200
        assert response.json()["deleted_commit_ids"] == ["commit-1"]
    finally:
        app.dependency_overrides.clear()


def test_scene_render_and_complete_endpoints(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    render_payload = {
        "voice_dna": "dna",
        "conflict_type": "internal",
        "outline_requirement": "keep the plan",
        "user_intent": "advance the plot",
        "expected_outcome": "Outcome 1",
        "world_state": {"hp": "100%"},
    }
    try:
        render = client.post(
            "/api/v1/scenes/scene-alpha/render",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json=render_payload,
        )
        assert render.status_code == 200
        assert render.json()["content"] == "Rendered text"

        completed = client.post(
            "/api/v1/scenes/scene-alpha/complete",
            params={"branch_id": DEFAULT_BRANCH_ID},
            json={"actual_outcome": "Done", "summary": "Summary"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "committed"
    finally:
        app.dependency_overrides.clear()


def test_fork_and_reset_branch_endpoints(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        fork_commit = client.post(
            "/api/v1/roots/root-alpha/branches/fork_from_commit",
            json={"source_commit_id": "c1", "new_branch_id": "dev"},
        )
        assert fork_commit.status_code == 200
        assert fork_commit.json()["branch_id"] == "dev"

        fork_scene = client.post(
            "/api/v1/roots/root-alpha/branches/fork_from_scene",
            json={
                "source_branch_id": DEFAULT_BRANCH_ID,
                "scene_origin_id": "scene-alpha",
                "new_branch_id": "dev2",
            },
        )
        assert fork_scene.status_code == 200
        assert fork_scene.json()["branch_id"] == "dev2"

        reset = client.post(
            f"/api/v1/roots/root-alpha/branches/{DEFAULT_BRANCH_ID}/reset",
            json={"commit_id": "c1"},
        )
        assert reset.status_code == 200
        assert reset.json()["branch_id"] == DEFAULT_BRANCH_ID
    finally:
        app.dependency_overrides.clear()


def test_branch_history_endpoint(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/roots/root-alpha/branches/{DEFAULT_BRANCH_ID}/history",
            params={"limit": 1},
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == "commit-1"
    finally:
        app.dependency_overrides.clear()



def test_logic_check_with_root_applies_impact_level(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    payload = {
        "outline_requirement": "outline",
        "world_state": {"hp": "100%"},
        "user_intent": "intent",
        "mode": "standard",
        "root_id": "root",
        "branch_id": DEFAULT_BRANCH_ID,
        "scene_id": "scene-alpha",
    }
    try:
        response = client.post("/api/v1/logic/check", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert storage.logic_world_state_calls == [("root", DEFAULT_BRANCH_ID, "scene-alpha")]
        assert storage.local_fixes == [("root", DEFAULT_BRANCH_ID, "scene-alpha", 3)]
    finally:
        app.dependency_overrides.clear()


def test_state_extract_enriches_when_root_provided(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    storage = DummyStorage()
    storage.states["entity-1"] = {"hp": "100%"}
    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    payload = {
        "content": "text",
        "entity_ids": ["entity-1"],
        "root_id": "root",
        "branch_id": DEFAULT_BRANCH_ID,
    }
    try:
        response = client.post("/api/v1/state/extract", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result[0]["semantic_states_before"] == {"hp": "100%"}
        assert result[0]["semantic_states_after"]["hp"] == "90%"
        assert storage.required == [("root", DEFAULT_BRANCH_ID)]
    finally:
        app.dependency_overrides.clear()


def test_complete_scene_orchestrated_force_execute(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()

    client = TestClient(app)
    payload = {
        "root_id": "root",
        "branch_id": DEFAULT_BRANCH_ID,
        "outline_requirement": "outline",
        "world_state": {"hp": "100%"},
        "user_intent": "intent",
        "mode": "force_execute",
        "force_reason": "override",
        "content": "story text",
        "entity_ids": ["entity-1"],
        "confirmed_proposals": [
            {
                "entity_id": "entity-1",
                "confidence": 0.9,
                "semantic_states_patch": {"hp": "80%"},
            }
        ],
        "actual_outcome": "Outcome",
        "summary": "Summary",
    }
    try:
        response = client.post(
            "/api/v1/scenes/scene-alpha/complete/orchestrated", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["confirmed_count"] == 1
        assert data["applied"] == 1
        assert storage.completed["scene-alpha"]["actual_outcome"] == "Outcome"
        assert storage.logic_exceptions[("root", DEFAULT_BRANCH_ID, "scene-alpha")] == "override"
    finally:
        app.dependency_overrides.clear()



def test_merge_and_revert_branch_endpoints(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    storage.branches.add("dev")
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        merged = client.post("/api/v1/roots/root-alpha/branches/dev/merge")
        assert merged.status_code == 200
        assert merged.json()["branch_id"] == "dev"

        reverted = client.post("/api/v1/roots/root-alpha/branches/dev/revert")
        assert reverted.status_code == 200
        assert reverted.json()["branch_id"] == "dev"
    finally:
        app.dependency_overrides.clear()


def test_llm_settings_round_trip() -> None:
    client = TestClient(app)
    original_response = client.get('/api/v1/settings/llm')
    assert original_response.status_code == 200
    original_payload = original_response.json()

    updated_payload = {
        'llm_config': {
            'model': 'gpt-4.1-mini',
            'temperature': 0.35,
            'max_tokens': 2048,
            'timeout': 30,
            'system_instruction': 'Keep responses concise.',
        },
        'system_config': {
            'auto_save': False,
            'ui_density': 'compact',
        },
    }

    try:
        update_response = client.put('/api/v1/settings/llm', json=updated_payload)
        assert update_response.status_code == 200
        assert update_response.json() == updated_payload

        read_back_response = client.get('/api/v1/settings/llm')
        assert read_back_response.status_code == 200
        assert read_back_response.json() == updated_payload
    finally:
        reset_response = client.put('/api/v1/settings/llm', json=original_payload)
        assert reset_response.status_code == 200



def test_llm_settings_rejects_malicious_model_values() -> None:
    client = TestClient(app)
    invalid_payloads = [
        {
            "llm_config": {
                "model": "<script>alert(1)</script>",
                "temperature": 0.3,
                "max_tokens": 2048,
                "timeout": 30,
                "system_instruction": "safe",
            },
            "system_config": {
                "auto_save": False,
                "ui_density": "compact",
            },
        },
        {
            "llm_config": {
                "model": "select * from users;--",
                "temperature": 0.3,
                "max_tokens": 2048,
                "timeout": 30,
                "system_instruction": "safe",
            },
            "system_config": {
                "auto_save": False,
                "ui_density": "compact",
            },
        },
        {
            "llm_config": {
                "model": "m" * 256,
                "temperature": 0.3,
                "max_tokens": 2048,
                "timeout": 30,
                "system_instruction": "safe",
            },
            "system_config": {
                "auto_save": False,
                "ui_density": "compact",
            },
        },
    ]

    for payload in invalid_payloads:
        response = client.put("/api/v1/settings/llm", json=payload)
        assert response.status_code == 422
        assert response.json()["detail"]




def test_step1_returns_503_when_engine_missing(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_ENGINE", raising=False)
    app.dependency_overrides[get_graph_storage] = lambda: DummyStorage()

    client = TestClient(app)
    try:
        response = client.post("/api/v1/snowflake/step1", json={"idea": "test idea"})
        assert response.status_code == 503
        assert "SNOWFLAKE_ENGINE" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()



def test_create_root_returns_503_when_memgraph_unavailable(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")

    def broken_host():
        raise RuntimeError("MEMGRAPH_HOST is required")

    import app.main as main

    monkeypatch.setattr(main, "require_memgraph_host", broken_host)
    main.get_graph_storage.cache_clear()

    client = TestClient(app)
    try:
        response = client.post("/api/v1/roots", json={"name": "示例项目"})
        assert response.status_code == 503
        assert "MEMGRAPH_HOST" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        main.get_graph_storage.cache_clear()



def test_step1_rejects_malicious_or_overlong_idea(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides[get_snowflake_manager] = lambda: DummyManager()

    client = TestClient(app)
    invalid_payloads = [
        {"idea": "<script>alert(1)</script>"},
        {"idea": "drop table users;--"},
        {"idea": "idea" * 1200},
    ]

    try:
        for payload in invalid_payloads:
            response = client.post("/api/v1/snowflake/step1", json=payload)
            assert response.status_code == 422
            assert response.json()["detail"]
    finally:
        app.dependency_overrides.clear()



def test_create_project_rejects_blank_name(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    client = TestClient(app)
    try:
        response = client.post("/api/v1/roots", json={"name": "   "})
        assert response.status_code == 422
        assert response.json()["detail"]
    finally:
        app.dependency_overrides.clear()

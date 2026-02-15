from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import app, get_graph_storage, get_topone_gateway


class DummyGateway:
    async def render_scene(self, payload):
        return "Rendered content"


class DummyStorage:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str]] = []

    def save_scene_render(self, *, scene_id: str, branch_id: str, content: str) -> None:
        self.saved.append((scene_id, branch_id, content))


@pytest.fixture()
def render_client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    storage = DummyStorage()

    app.dependency_overrides[get_topone_gateway] = lambda: DummyGateway()
    app.dependency_overrides[get_graph_storage] = lambda: storage

    with TestClient(app) as client:
        yield client, storage

    app.dependency_overrides.clear()


def _payload() -> dict:
    return {
        "voice_dna": "warm",
        "conflict_type": "internal",
        "outline_requirement": "scene outline",
        "user_intent": "render",
        "expected_outcome": "resolve conflict",
        "world_state": {"mood": "tense"},
    }


def _editor_view_content() -> str:
    repo_root = Path(__file__).resolve().parents[4]
    view_path = repo_root / "project" / "frontend" / "src" / "views" / "EditorView.vue"
    return view_path.read_text(encoding="utf-8")


def test_render_scene_empty_payload_returns_422(render_client):
    client, _ = render_client
    response = client.post("/api/v1/scenes/scene-alpha/render?branch_id=main", json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "missing_field",
    [
        "voice_dna",
        "conflict_type",
        "outline_requirement",
        "user_intent",
        "expected_outcome",
    ],
)
def test_render_scene_missing_required_field_returns_422(render_client, missing_field):
    client, _ = render_client
    payload = _payload()
    payload.pop(missing_field)

    response = client.post(
        "/api/v1/scenes/scene-alpha/render?branch_id=main", json=payload
    )

    assert response.status_code == 422


def test_render_scene_full_payload_returns_content(render_client):
    client, storage = render_client

    response = client.post(
        "/api/v1/scenes/scene-alpha/render?branch_id=main", json=_payload()
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "scene_id": "scene-alpha",
        "branch_id": "main",
        "content": "Rendered content",
    }
    assert storage.saved == [("scene-alpha", "main", "Rendered content")]


def test_frontend_render_scene_payload_contains_required_fields():
    content = _editor_view_content()
    required_fields = [
        "voice_dna",
        "conflict_type",
        "outline_requirement",
        "user_intent",
        "expected_outcome",
    ]

    missing = [field for field in required_fields if field not in content]

    assert not missing, f"missing render payload fields in EditorView: {missing}"

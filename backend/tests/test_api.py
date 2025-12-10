from fastapi.testclient import TestClient

from app.main import app, get_llm_engine, get_snowflake_manager, get_topone_client
from app.models import SceneNode, SnowflakeRoot
from app.services.topone_client import ToponeClient


class DummyEngine:
    async def generate_root_structure(self, logline: str) -> SnowflakeRoot:
        return SnowflakeRoot(
            logline="Test story",
            three_disasters=["D1", "D2", "D3"],
            ending="End",
            theme="Testing",
        )

    async def generate_scene_list(self, root, characters):
        return [
            SceneNode(
                expected_outcome="Outcome 1",
                conflict_type="internal",
                parent_act_id=None,
            )
        ]


def test_generate_structure_endpoint():
    app.dependency_overrides[get_llm_engine] = lambda: DummyEngine()
    client = TestClient(app)

    response = client.post("/api/v1/snowflake/step2", json={"logline": "raw idea"})
    assert response.status_code == 200

    data = response.json()
    assert data["logline"] == "Test story"
    assert len(data["three_disasters"]) == 3

    app.dependency_overrides.clear()


def test_generate_scene_endpoint():
    dummy_engine = DummyEngine()
    app.dependency_overrides[get_llm_engine] = lambda: dummy_engine
    app.dependency_overrides[get_snowflake_manager] = (
        lambda: None  # placeholder to satisfy dependency
    )
    # override manager with relaxed scene bounds
    from app.logic.snowflake_manager import SnowflakeManager

    app.dependency_overrides[get_snowflake_manager] = lambda: SnowflakeManager(
        engine=dummy_engine, min_scenes=1, max_scenes=5
    )
    client = TestClient(app)

    payload = {
        "root": {
            "logline": "Test story",
            "three_disasters": ["D1", "D2", "D3"],
            "ending": "End",
            "theme": "Testing",
        },
        "characters": [],
    }
    response = client.post("/api/v1/snowflake/step4", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert data[0]["expected_outcome"] == "Outcome 1"

    app.dependency_overrides.clear()


def test_negotiation_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws/negotiation") as websocket:
        websocket.send_json({"hello": "world"})
        data = websocket.receive_json()
        assert data == {"ack": {"hello": "world"}}


def test_topone_generate_endpoint(monkeypatch):
    class StubTopone(ToponeClient):
        async def generate_content(self, **kwargs):
            self.kwargs = kwargs
            return {"ok": True}

    stub = StubTopone(api_key="k")
    app.dependency_overrides[get_snowflake_manager] = lambda: None
    app.dependency_overrides[get_llm_engine] = lambda: DummyEngine()
    app.dependency_overrides[get_topone_client] = lambda: stub  # type: ignore[name-defined]

    client = TestClient(app)
    payload = {
        "model": "gemini-2.5-flash",
        "system_instruction": "sys",
        "messages": [{"role": "user", "text": "hi"}],
        "generation_config": {"temperature": 0.5},
        "timeout": 15,
    }
    response = client.post("/api/v1/llm/topone/generate", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert stub.kwargs["model"] == "gemini-2.5-flash"
    assert stub.kwargs["system_instruction"] == "sys"
    app.dependency_overrides.clear()

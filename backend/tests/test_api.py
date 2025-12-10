from fastapi.testclient import TestClient

from app.main import app, get_llm_engine, get_snowflake_manager
from app.models import SceneNode, SnowflakeRoot


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

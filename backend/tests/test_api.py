from fastapi.testclient import TestClient

from app.main import app, get_llm_engine
from app.models import SnowflakeRoot


class DummyEngine:
    async def generate_root_structure(self, logline: str) -> SnowflakeRoot:
        return SnowflakeRoot(
            logline="Test story",
            three_disasters=["D1", "D2", "D3"],
            ending="End",
            theme="Testing",
        )


def test_generate_structure_endpoint():
    app.dependency_overrides[get_llm_engine] = lambda: DummyEngine()
    client = TestClient(app)

    response = client.post("/api/v1/snowflake/step2", json={"logline": "raw idea"})
    assert response.status_code == 200

    data = response.json()
    assert data["logline"] == "Test story"
    assert len(data["three_disasters"]) == 3

    app.dependency_overrides.clear()


import pytest
from fastapi.testclient import TestClient

from app.llm.schemas import ImpactLevel, LogicCheckResult
from app.main import app, get_graph_storage, get_topone_gateway


class StubGraphStorage:
    def __init__(self, *, world_state: dict) -> None:
        self._world_state = world_state
        self.build_world_state_calls: list[dict[str, str]] = []

    # NOTE: This method name is intentionally chosen by tests to drive DEV implementation.
    def build_logic_check_world_state(self, *, root_id: str, branch_id: str, scene_id: str) -> dict:
        self.build_world_state_calls.append(
            {"root_id": root_id, "branch_id": branch_id, "scene_id": scene_id}
        )
        return self._world_state


class StubGateway:
    def __init__(self) -> None:
        self.seen_payloads: list = []

    async def logic_check(self, payload):
        self.seen_payloads.append(payload)
        # Return ok=False so the endpoint returns early and doesn't touch storage
        # beyond building world_state (which is what this test cares about).
        return LogicCheckResult(
            ok=False,
            mode=payload.mode,
            decision="reject",
            impact_level=ImpactLevel.NEGLIGIBLE,
        )


def test_logic_check_with_locator_builds_world_state_from_storage(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")

    request_world_state = {"from_request": True}
    storage_world_state = {"from_storage": True}
    storage = StubGraphStorage(world_state=storage_world_state)
    gateway = StubGateway()

    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: gateway
    client = TestClient(app)

    try:
        payload = {
            "outline_requirement": "outline",
            "world_state": request_world_state,
            "user_intent": "intent",
            "mode": "standard",
            "root_id": "root_1",
            "branch_id": "branch_1",
            "scene_id": "scene_1",
        }
        response = client.post("/api/v1/logic/check", json=payload)
        assert response.status_code == 200

        assert gateway.seen_payloads, "gateway.logic_check should be invoked"
        seen = gateway.seen_payloads[-1]

        # Expectation for M2-T2:
        # - When locator is present, endpoint must ignore request body world_state
        # - Build world_state from graph storage and pass it into gateway
        assert seen.world_state == storage_world_state
        assert seen.world_state != request_world_state
        assert storage.build_world_state_calls == [
            {"root_id": "root_1", "branch_id": "branch_1", "scene_id": "scene_1"}
        ]
    finally:
        app.dependency_overrides.clear()


def test_logic_check_without_locator_uses_request_world_state(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")

    request_world_state = {"from_request": True}
    storage = StubGraphStorage(world_state={"from_storage": True})
    gateway = StubGateway()

    app.dependency_overrides[get_graph_storage] = lambda: storage
    app.dependency_overrides[get_topone_gateway] = lambda: gateway
    client = TestClient(app)

    try:
        payload = {
            "outline_requirement": "outline",
            "world_state": request_world_state,
            "user_intent": "intent",
            "mode": "standard",
        }
        response = client.post("/api/v1/logic/check", json=payload)
        assert response.status_code == 200

        assert gateway.seen_payloads, "gateway.logic_check should be invoked"
        seen = gateway.seen_payloads[-1]
        assert seen.world_state == request_world_state
        assert storage.build_world_state_calls == []
    finally:
        app.dependency_overrides.clear()

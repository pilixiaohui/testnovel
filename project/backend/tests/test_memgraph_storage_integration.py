import importlib
import os
import sys
import types

import pytest


def _get_memgraph_connection_config() -> tuple[str, str, str]:
    uri = os.getenv("MEMGRAPH_BOLT_URI") or os.getenv("MEMGRAPH_URI")
    if not uri:
        raise RuntimeError("MEMGRAPH_BOLT_URI or MEMGRAPH_URI is required")
    username = os.getenv("MEMGRAPH_USERNAME", "")
    password = os.getenv("MEMGRAPH_PASSWORD", "")
    return uri, username, password


@pytest.fixture()
def memgraph_storage():
    try:
        module = importlib.import_module("app.storage.memgraph_world_state")
    except ModuleNotFoundError as exc:
        assert False, (
            "Memgraph storage implementation is missing. "
            "Expected: app.storage.memgraph_world_state.MemgraphWorldStateStorage. "
            f"Import error: {exc}"
        )

    storage_cls = getattr(module, "MemgraphWorldStateStorage", None)
    assert storage_cls is not None, (
        "Memgraph storage implementation is missing. "
        "Expected: app.storage.memgraph_world_state.MemgraphWorldStateStorage"
    )

    uri, username, password = _get_memgraph_connection_config()
    try:
        storage = storage_cls(uri=uri, username=username, password=password)
    except Exception as exc:
        if os.getenv("REQUIRE_MEMGRAPH", "").lower() in {"1", "true", "yes"}:
            raise
        pytest.skip(
            "Memgraph is not available.\n"
            "Start it via Docker Compose:\n"
            "  MEMGRAPH_IMAGE=<your-image> docker compose -f project/backend/docker-compose.memgraph.yml up -d\n"
            "Or point tests at an existing Memgraph:\n"
            "  MEMGRAPH_BOLT_URI=bolt://<host>:7687\n"
            "Set REQUIRE_MEMGRAPH=1 to fail instead of skip.\n"
            f"Connection error: {exc}"
        )

    storage.clear_all()
    try:
        yield storage
    finally:
        storage.clear_all()
        storage.close()

def test_get_memgraph_connection_config_prefers_memgraph_bolt_uri(monkeypatch):
    monkeypatch.setenv("MEMGRAPH_BOLT_URI", "bolt://example:7687")
    monkeypatch.setenv("MEMGRAPH_URI", "bolt://should-not-win:7687")

    uri, _, _ = _get_memgraph_connection_config()
    assert uri == "bolt://example:7687"


def test_get_memgraph_connection_config_falls_back_to_memgraph_uri(monkeypatch):
    monkeypatch.delenv("MEMGRAPH_BOLT_URI", raising=False)
    monkeypatch.setenv("MEMGRAPH_URI", "bolt://example:7687")

    uri, _, _ = _get_memgraph_connection_config()
    assert uri == "bolt://example:7687"


def test_get_memgraph_connection_config_requires_uri(monkeypatch):
    monkeypatch.delenv("MEMGRAPH_BOLT_URI", raising=False)
    monkeypatch.delenv("MEMGRAPH_URI", raising=False)

    with pytest.raises(RuntimeError, match="MEMGRAPH_BOLT_URI or MEMGRAPH_URI is required"):
        _get_memgraph_connection_config()


def test_memgraph_storage_skips_with_guidance_when_unavailable(monkeypatch, request):
    fake_module = types.ModuleType("app.storage.memgraph_world_state")

    class FakeStorage:
        def __init__(self, uri: str, username: str, password: str):
            raise RuntimeError("boom")

    fake_module.MemgraphWorldStateStorage = FakeStorage
    monkeypatch.setitem(sys.modules, "app.storage.memgraph_world_state", fake_module)
    monkeypatch.delenv("REQUIRE_MEMGRAPH", raising=False)

    with pytest.raises(pytest.skip.Exception) as excinfo:
        request.getfixturevalue("memgraph_storage")

    msg = str(excinfo.value)
    assert "MEMGRAPH_IMAGE" in msg
    assert "MEMGRAPH_BOLT_URI" in msg
    assert "REQUIRE_MEMGRAPH=1" in msg


def test_memgraph_storage_raises_when_require_memgraph(monkeypatch, request):
    fake_module = types.ModuleType("app.storage.memgraph_world_state")

    class FakeStorage:
        def __init__(self, uri: str, username: str, password: str):
            raise RuntimeError("boom")

    fake_module.MemgraphWorldStateStorage = FakeStorage
    monkeypatch.setitem(sys.modules, "app.storage.memgraph_world_state", fake_module)
    monkeypatch.setenv("REQUIRE_MEMGRAPH", "1")

    with pytest.raises(RuntimeError, match="boom"):
        request.getfixturevalue("memgraph_storage")


def test_memgraph_minimal_closed_loop(memgraph_storage):
    # 1) 写入/读取 entity 状态（包含 start_scene_seq/end_scene_seq）
    entity_a = memgraph_storage.add_entity_state(
        entity_id="entity-a",
        semantic_states={"hp": "100%"},
        start_scene_seq=1,
        end_scene_seq=3,
    )
    assert entity_a.entity_id == "entity-a"
    assert entity_a.start_scene_seq == 1
    assert entity_a.end_scene_seq == 3
    assert entity_a.semantic_states == {"hp": "100%"}

    states_a = memgraph_storage.list_entity_states(entity_id="entity-a")
    assert len(states_a) == 1
    assert states_a[0].start_scene_seq == 1
    assert states_a[0].end_scene_seq == 3
    assert states_a[0].semantic_states == {"hp": "100%"}

    memgraph_storage.add_entity_state(
        entity_id="entity-b",
        semantic_states={"location": "town"},
        start_scene_seq=2,
        end_scene_seq=4,
    )

    # 2) 按 scene_seq 查询 world_state
    assert memgraph_storage.get_world_state(scene_seq=1) == {"entity-a": {"hp": "100%"}}
    assert memgraph_storage.get_world_state(scene_seq=2) == {
        "entity-a": {"hp": "100%"},
        "entity-b": {"location": "town"},
    }

    # 3) 生成并读取 snapshot
    snapshot = memgraph_storage.create_snapshot(scene_seq=2)
    loaded = memgraph_storage.get_snapshot(snapshot_id=snapshot.snapshot_id)
    assert loaded.scene_seq == 2
    assert loaded.world_state == {
        "entity-a": {"hp": "100%"},
        "entity-b": {"location": "town"},
    }

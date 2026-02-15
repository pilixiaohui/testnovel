import pytest

import app.main as main

from app.llm.schemas import ImpactLevel, StateProposal
from app.main import (
    _apply_impact_level,
    _apply_state_proposals,
    _enrich_state_proposals,
    _require_snowflake_engine_mode,
)
from app.services.llm_engine import LLMEngine, LocalStoryEngine


class DummyStorage:
    def __init__(self) -> None:
        self.required: list[tuple[str, str]] = []
        self.patches: list[tuple[str, str, str, dict]] = []
        self.local_calls: list[tuple[str, str, str, int]] = []
        self.cascade_calls: list[tuple[str, str, str]] = []

    def require_root(self, *, root_id: str, branch_id: str) -> None:
        self.required.append((root_id, branch_id))

    def get_entity_semantic_states(
        self, *, root_id: str, branch_id: str, entity_id: str
    ) -> dict:
        return {"mood": "steady"}

    def apply_semantic_states_patch(
        self, *, root_id: str, branch_id: str, entity_id: str, patch: dict
    ) -> dict:
        updated = {"mood": "steady"}
        updated.update(patch)
        self.patches.append((root_id, branch_id, entity_id, patch))
        return updated

    def apply_local_scene_fix(
        self, *, root_id: str, branch_id: str, scene_id: str, limit: int = 3
    ) -> list[str]:
        self.local_calls.append((root_id, branch_id, scene_id, limit))
        return ["scene-local"]

    def mark_future_scenes_dirty(
        self, *, root_id: str, branch_id: str, scene_id: str
    ) -> list[str]:
        self.cascade_calls.append((root_id, branch_id, scene_id))
        return ["scene-cascading"]


def test_require_snowflake_engine_mode_missing(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_ENGINE", raising=False)
    with pytest.raises(RuntimeError, match="SNOWFLAKE_ENGINE"):
        _require_snowflake_engine_mode()


def test_require_snowflake_engine_mode_invalid(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "invalid")
    with pytest.raises(RuntimeError, match="SNOWFLAKE_ENGINE"):
        _require_snowflake_engine_mode()


def test_require_snowflake_engine_mode_valid(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    assert _require_snowflake_engine_mode() == "local"


def test_apply_state_proposals_rejects_empty():
    storage = DummyStorage()
    with pytest.raises(ValueError, match="proposals must not be empty"):
        _apply_state_proposals(
            storage=storage, root_id="root", branch_id="branch", proposals=[]
        )


def test_apply_state_proposals_updates_entities():
    storage = DummyStorage()
    proposals = [
        StateProposal(
            entity_id="entity-1", confidence=0.9, semantic_states_patch={"hp": "90%"}
        )
    ]
    updated = _apply_state_proposals(
        storage=storage, root_id="root", branch_id="branch", proposals=proposals
    )
    assert updated == [
        {"entity_id": "entity-1", "semantic_states": {"mood": "steady", "hp": "90%"}}
    ]
    assert storage.required == [("root", "branch")]


def test_enrich_state_proposals_attaches_states():
    storage = DummyStorage()
    proposals = [
        StateProposal(
            entity_id="entity-1", confidence=0.9, semantic_states_patch={"hp": "90%"}
        )
    ]
    enriched = _enrich_state_proposals(
        storage=storage, root_id="root", branch_id="branch", proposals=proposals
    )
    assert enriched[0].semantic_states_before == {"mood": "steady"}
    assert enriched[0].semantic_states_after == {"mood": "steady", "hp": "90%"}
    assert storage.required == [("root", "branch")]


def test_apply_impact_level_negligible_returns_empty():
    storage = DummyStorage()
    assert (
        _apply_impact_level(
            storage=storage,
            root_id="root",
            branch_id="branch",
            scene_id="scene",
            impact_level=ImpactLevel.NEGLIGIBLE,
        )
        == []
    )
    assert storage.local_calls == []
    assert storage.cascade_calls == []


def test_apply_impact_level_routes_to_storage():
    storage = DummyStorage()
    assert (
        _apply_impact_level(
            storage=storage,
            root_id="root",
            branch_id="branch",
            scene_id="scene",
            impact_level=ImpactLevel.LOCAL,
        )
        == ["scene-local"]
    )
    assert (
        _apply_impact_level(
            storage=storage,
            root_id="root",
            branch_id="branch",
            scene_id="scene",
            impact_level=ImpactLevel.CASCADING,
        )
        == ["scene-cascading"]
    )
    assert storage.local_calls == [("root", "branch", "scene", 3)]
    assert storage.cascade_calls == [("root", "branch", "scene")]


def test_get_llm_engine_local_returns_local_story_engine(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    engine = main.get_llm_engine()
    assert isinstance(engine, LocalStoryEngine)


def test_get_llm_engine_llm_returns_llm_engine(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "llm")
    engine = main.get_llm_engine()
    assert isinstance(engine, LLMEngine)


def test_get_llm_engine_gemini_uses_topone_gateway(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "gemini")
    sentinel = object()
    monkeypatch.setattr(main, "get_topone_gateway", lambda: sentinel)
    assert main.get_llm_engine() is sentinel


def test_get_graph_storage_uses_memgraph_config(monkeypatch):
    calls: dict[str, bool] = {}

    def fake_host():
        calls["host"] = True
        return "memgraph-host"

    def fake_port():
        calls["port"] = True
        return 7687

    monkeypatch.setattr(main, "require_memgraph_host", fake_host)
    monkeypatch.setattr(main, "require_memgraph_port", fake_port)

    import app.storage.memgraph_storage as memgraph_storage

    class DummyStorage:
        def __init__(self, *, host: str, port: int) -> None:
            self.host = host
            self.port = port

    monkeypatch.setattr(memgraph_storage, "MemgraphStorage", DummyStorage)

    main.get_graph_storage.cache_clear()
    try:
        storage = main.get_graph_storage()
        assert storage.host == "memgraph-host"
        assert storage.port == 7687
        assert calls == {"host": True, "port": True}
    finally:
        main.get_graph_storage.cache_clear()



def test_get_snowflake_manager_uses_scene_limits():
    dummy_engine = object()
    dummy_storage = object()
    manager = main.get_snowflake_manager(engine=dummy_engine, storage=dummy_storage)
    assert manager.engine is dummy_engine
    assert manager.storage is dummy_storage
    assert manager.min_scenes == main.SCENE_MIN_COUNT
    assert manager.max_scenes == main.SCENE_MAX_COUNT

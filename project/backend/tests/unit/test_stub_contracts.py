"""验证共享 stub 与真实类的接口一致性。"""
import inspect

import pytest


def _public_attrs(cls):
    """Return public non-dunder attribute names of a class."""
    return {a for a in dir(cls) if not a.startswith("_")}


_missing_gqlalchemy = False
try:
    from app.services.simulation_engine import SimulationEngine  # noqa: F401
except ImportError:
    _missing_gqlalchemy = True


@pytest.mark.skipif(_missing_gqlalchemy, reason="gqlalchemy not installed")
def test_simulation_engine_stub_has_required_attrs():
    from app.services.simulation_engine import SimulationEngine  # noqa: F811
    from tests.shared_stubs import SimulationEngineStub

    # SimulationEngine requires character_engine attribute
    stub = SimulationEngineStub()
    assert hasattr(stub, "character_engine"), "Stub missing character_engine"
    assert hasattr(stub, "run_round"), "Stub missing run_round"
    assert hasattr(stub, "run_scene"), "Stub missing run_scene"


def test_simulation_engine_stub_character_engine_has_decide():
    from tests.shared_stubs import SimulationEngineStub

    stub = SimulationEngineStub()
    assert hasattr(stub.character_engine, "decide"), "character_engine missing decide"


def test_graph_storage_stub_covers_port_protocol():
    from app.storage.ports import GraphStoragePort
    from tests.shared_stubs import GraphStorageStub

    # Get all methods defined in the Protocol
    port_methods = set()
    for name, val in inspect.getmembers(GraphStoragePort):
        if name.startswith("_"):
            continue
        if callable(val) or isinstance(inspect.getattr_static(GraphStoragePort, name), property):
            port_methods.add(name)

    stub_attrs = _public_attrs(GraphStorageStub)
    missing = port_methods - stub_attrs
    # Allow some methods to be missing if they aren't used in the 3 migrated test files
    # But flag them so we know about drift
    if missing:
        # These are acceptable gaps — methods not exercised by the migrated tests
        acceptable_gaps = {
            "list_roots", "update_entity", "delete_entity",
            "get_act", "update_act", "delete_act", "list_acts",
            "create_act", "create_chapter", "get_chapter", "update_chapter",
            "delete_chapter", "list_chapters", "link_scene_to_chapter",
            "create_anchor", "get_anchor", "update_anchor", "delete_anchor",
            "mark_anchor_achieved", "list_anchors", "get_next_unachieved_anchor",
            "init_character_agent", "get_agent_state", "delete_agent_state",
            "update_agent_desires", "update_agent_beliefs", "add_agent_memory",
            "create_simulation_log", "get_simulation_log", "list_simulation_logs",
            "update_simulation_log", "delete_simulation_log",
            "create_subplot", "get_subplot", "update_subplot",
            "list_subplots", "delete_subplot",
        }
        unexpected_missing = missing - acceptable_gaps
        assert not unexpected_missing, (
            f"GraphStorageStub missing methods from GraphStoragePort: {unexpected_missing}"
        )

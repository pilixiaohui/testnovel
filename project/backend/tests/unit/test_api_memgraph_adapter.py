import importlib
import inspect

import pytest

from app.storage.ports import GraphStoragePort


def _load_memgraph_storage():
    try:
        module = importlib.import_module("app.storage.memgraph_storage")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.storage.memgraph_storage is missing: {exc}", pytrace=False)
    if not hasattr(module, "MemgraphStorage"):
        pytest.fail("MemgraphStorage class is missing", pytrace=False)
    return module.MemgraphStorage


def _graph_storage_port_methods() -> list[str]:
    methods: list[str] = []
    for name, member in GraphStoragePort.__dict__.items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(member):
            methods.append(name)
    return sorted(methods)


def test_memgraph_storage_implements_graph_storage_port_methods():
    storage_cls = _load_memgraph_storage()
    missing = [name for name in _graph_storage_port_methods() if not hasattr(storage_cls, name)]
    if missing:
        pytest.fail(
            "MemgraphStorage must implement GraphStoragePort methods for API adaptation: "
            + ", ".join(missing),
            pytrace=False,
        )


def test_memgraph_storage_supports_migration_target_interface():
    storage_cls = _load_memgraph_storage()
    required = ["insert_nodes", "insert_edges", "delete_nodes", "delete_edges", "snapshot"]
    missing = [name for name in required if not hasattr(storage_cls, name)]
    if missing:
        pytest.fail(
            "MemgraphStorage must support migration target interface: " + ", ".join(missing),
            pytrace=False,
        )

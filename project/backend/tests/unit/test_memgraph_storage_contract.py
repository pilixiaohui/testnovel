import importlib
import importlib.util
import inspect

import pytest


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        assert False, f"{module_path} module is missing: {exc}"
    assert spec is not None, f"{module_path} module is missing"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        assert False, f"failed to import {module_path}: {exc}"


def _import_memgraph_storage_module():
    return _import_module("app.storage.memgraph_storage")


def _assert_method_min_params(cls: type, name: str, min_params: int) -> None:
    assert hasattr(cls, name), f"MemgraphStorage.{name} is missing"
    method = getattr(cls, name)
    assert callable(method), f"MemgraphStorage.{name} must be callable"
    signature = inspect.signature(method)
    assert (
        len(signature.parameters) >= min_params
    ), f"MemgraphStorage.{name} must accept at least {min_params} parameters"


def test_memgraph_storage_module_exists():
    _import_module("app.storage.memgraph_storage")


def test_memgraph_storage_class_and_crud_signatures():
    module = _import_memgraph_storage_module()
    assert hasattr(module, "MemgraphStorage"), "MemgraphStorage class is missing"
    storage_cls = module.MemgraphStorage
    assert inspect.isclass(storage_cls), "MemgraphStorage must be a class"

    required_methods = {
        "create_root": 2,
        "get_root": 2,
        "update_root": 2,
        "delete_root": 2,
    }
    for name, min_params in required_methods.items():
        _assert_method_min_params(storage_cls, name, min_params)


def test_memgraph_storage_rejects_missing_root_id():
    module = _import_memgraph_storage_module()
    storage = module.MemgraphStorage()

    class DummyNode:
        pass

    with pytest.raises(ValueError, match="node id is required"):
        storage.db.save_node(DummyNode())


class _DummyDB:
    def execute_and_fetch(self, *args, **kwargs):
        return iter(())


def _build_storage():
    module = _import_memgraph_storage_module()
    storage = module.MemgraphStorage.__new__(module.MemgraphStorage)
    storage.db = _DummyDB()
    storage._require_root_node = lambda *args, **kwargs: None
    storage._require_branch_node = lambda *args, **kwargs: None
    storage._create_node = lambda *args, **kwargs: None
    return storage, module


def _any_valid_constraint(constraints: set[str]) -> str:
    return next(iter(constraints))


def test_anchor_types_include_required():
    module = _import_memgraph_storage_module()
    required = {"inciting_incident", "midpoint", "climax", "resolution"}
    missing = required - module.VALID_ANCHOR_TYPES
    assert not missing, f"VALID_ANCHOR_TYPES missing: {sorted(missing)}"


def test_anchor_constraints_include_required():
    module = _import_memgraph_storage_module()
    required = {"hard", "soft", "flexible"}
    missing = required - module.VALID_ANCHOR_CONSTRAINTS
    assert not missing, f"VALID_ANCHOR_CONSTRAINTS missing: {sorted(missing)}"


def test_create_anchor_accepts_all_valid_types():
    storage, module = _build_storage()
    constraint = _any_valid_constraint(module.VALID_ANCHOR_CONSTRAINTS)
    for idx, anchor_type in enumerate(module.VALID_ANCHOR_TYPES, start=1):
        result = storage.create_anchor(
            root_id="root-alpha",
            branch_id="main",
            seq=idx,
            type=anchor_type,
            desc="desc",
            constraint=constraint,
            conditions="[]",
        )
        assert result["anchor_type"] == anchor_type


def test_create_anchor_rejects_invalid_type():
    storage, module = _build_storage()
    constraint = _any_valid_constraint(module.VALID_ANCHOR_CONSTRAINTS)
    invalid = "invalid_anchor_type"
    assert invalid not in module.VALID_ANCHOR_TYPES
    with pytest.raises(ValueError, match="invalid anchor type"):
        storage.create_anchor(
            root_id="root-alpha",
            branch_id="main",
            seq=1,
            type=invalid,
            desc="desc",
            constraint=constraint,
            conditions="[]",
        )

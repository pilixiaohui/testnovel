import importlib
import importlib.util
import inspect

import pytest


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{module_path} module is missing: {exc}", pytrace=False)
    if spec is None:
        pytest.fail(f"{module_path} module is missing", pytrace=False)
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_memgraph_storage_class():
    module = _import_module("app.storage.memgraph_storage")
    if not hasattr(module, "MemgraphStorage"):
        pytest.fail("MemgraphStorage class is missing", pytrace=False)
    return module.MemgraphStorage


def _require_method(cls: type, name: str):
    if not hasattr(cls, name):
        pytest.fail(f"MemgraphStorage.{name} is missing", pytrace=False)
    method = getattr(cls, name)
    if not callable(method):
        pytest.fail(f"MemgraphStorage.{name} must be callable", pytrace=False)
    return method


def _require_params(method, required: list[str]) -> None:
    signature = inspect.signature(method)
    params = signature.parameters
    missing = [name for name in required if name not in params]
    if missing:
        pytest.fail(
            f"{method.__qualname__} missing params: {missing}",
            pytrace=False,
        )


def test_memgraph_storage_m2_methods_exist():
    storage_cls = _get_memgraph_storage_class()

    required_methods = [
        "create_act",
        "get_act",
        "update_act",
        "delete_act",
        "list_acts",
        "create_chapter",
        "get_chapter",
        "update_chapter",
        "delete_chapter",
        "list_chapters",
        "link_scene_to_chapter",
        "create_anchor",
        "get_anchor",
        "update_anchor",
        "delete_anchor",
        "mark_anchor_achieved",
        "get_next_unachieved_anchor",
        "init_character_agent",
        "get_agent_state",
        "delete_agent_state",
        "update_agent_beliefs",
        "add_agent_memory",
        "create_simulation_log",
        "get_simulation_log",
        "update_simulation_log",
        "delete_simulation_log",
        "create_subplot",
        "get_subplot",
        "update_subplot",
        "delete_subplot",
    ]

    for name in required_methods:
        _require_method(storage_cls, name)


def test_memgraph_storage_m2_signatures():
    storage_cls = _get_memgraph_storage_class()

    _require_params(
        _require_method(storage_cls, "create_act"),
        ["root_id", "seq", "title", "purpose", "tone"],
    )
    _require_params(
        _require_method(storage_cls, "list_acts"),
        ["root_id"],
    )
    _require_params(
        _require_method(storage_cls, "create_chapter"),
        ["act_id", "seq", "title", "focus"],
    )
    _require_params(
        _require_method(storage_cls, "list_chapters"),
        ["act_id"],
    )
    _require_params(
        _require_method(storage_cls, "link_scene_to_chapter"),
        ["scene_id", "chapter_id"],
    )
    _require_params(
        _require_method(storage_cls, "create_anchor"),
        ["root_id", "branch_id", "seq", "type", "desc", "constraint", "conditions"],
    )
    _require_params(
        _require_method(storage_cls, "mark_anchor_achieved"),
        ["anchor_id", "scene_version_id"],
    )
    _require_params(
        _require_method(storage_cls, "get_next_unachieved_anchor"),
        ["root_id", "branch_id"],
    )
    _require_params(
        _require_method(storage_cls, "init_character_agent"),
        ["char_id", "branch_id", "initial_desires"],
    )
    _require_params(
        _require_method(storage_cls, "update_agent_beliefs"),
        ["agent_id", "beliefs_patch"],
    )
    _require_params(
        _require_method(storage_cls, "add_agent_memory"),
        ["agent_id", "entry"],
    )

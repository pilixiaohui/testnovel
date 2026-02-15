import importlib
import importlib.util
import inspect
from types import SimpleNamespace

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
    except ImportError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_subplot_manager_class():
    module = _import_module("app.services.subplot_manager")
    if not hasattr(module, "SubplotManager"):
        pytest.fail("SubplotManager class is missing", pytrace=False)
    manager_cls = module.SubplotManager
    if not inspect.isclass(manager_cls):
        pytest.fail("SubplotManager must be a class", pytrace=False)
    return manager_cls


def _build_subplot(status: str = "dormant"):
    return SimpleNamespace(
        id="subplot-1",
        root_id="root-alpha",
        branch_id="branch-1",
        title="subplot",
        subplot_type="mystery",
        protagonist_id="entity-1",
        central_conflict="conflict",
        status=status,
    )


class StorageStub:
    def __init__(self):
        self.updated: list[object] = []

    def update_subplot(self, subplot: object):
        self.updated.append(subplot)
        return subplot


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


def test_subplot_manager_module_exists():
    _import_module("app.services.subplot_manager")


def test_subplot_manager_exposes_activation_and_resolution():
    manager_cls = _get_subplot_manager_class()
    for name in ("activate_subplot", "resolve_subplot"):
        if not hasattr(manager_cls, name):
            pytest.fail(f"SubplotManager.{name} is missing", pytrace=False)
        if not callable(getattr(manager_cls, name)):
            pytest.fail(f"SubplotManager.{name} must be callable", pytrace=False)


@pytest.mark.asyncio
async def test_activate_subplot_updates_status_and_storage():
    manager_cls = _get_subplot_manager_class()
    storage = StorageStub()
    try:
        manager = manager_cls(storage)
    except TypeError:
        pytest.fail("SubplotManager must accept storage", pytrace=False)

    subplot = _build_subplot(status="dormant")
    result = await _await_if_needed(manager.activate_subplot(subplot))

    assert result.status == "active"
    assert storage.updated
    assert storage.updated[-1].status == "active"


@pytest.mark.asyncio
async def test_resolve_subplot_updates_status_and_storage():
    manager_cls = _get_subplot_manager_class()
    storage = StorageStub()
    manager = manager_cls(storage)

    subplot = _build_subplot(status="active")
    result = await _await_if_needed(manager.resolve_subplot(subplot))

    assert result.status == "resolved"
    assert storage.updated
    assert storage.updated[-1].status == "resolved"


@pytest.mark.asyncio
async def test_resolve_subplot_requires_active_status():
    manager_cls = _get_subplot_manager_class()
    storage = StorageStub()
    manager = manager_cls(storage)

    subplot = _build_subplot(status="dormant")
    with pytest.raises(ValueError):
        await _await_if_needed(manager.resolve_subplot(subplot))
    assert not storage.updated

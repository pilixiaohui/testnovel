import importlib
import importlib.util
import os

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
        missing = exc.name
        if missing in {"gqlalchemy"}:
            pytest.fail(
                f"{module_path} requires {missing} but it is missing: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        message = str(exc)
        if "gqlalchemy" in message:
            pytest.fail(
                f"{module_path} dependency import failed: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_memgraph_storage_class():
    module = _import_module("app.storage.memgraph_storage")
    if not hasattr(module, "MemgraphStorage"):
        pytest.fail("MemgraphStorage class is missing", pytrace=False)
    return module.MemgraphStorage


def _get_memgraph_connection_config() -> tuple[str, int]:
    host = os.getenv("MEMGRAPH_HOST")
    if not host:
        pytest.fail("MEMGRAPH_HOST is required", pytrace=False)
    raw_port = os.getenv("MEMGRAPH_PORT")
    if not raw_port:
        pytest.fail("MEMGRAPH_PORT is required", pytrace=False)
    try:
        port = int(raw_port)
    except ValueError as exc:
        pytest.fail(f"MEMGRAPH_PORT must be an integer: {exc}", pytrace=False)
    return host, port


def _assert_memgraph_connection(storage) -> None:
    if not hasattr(storage, "db"):
        pytest.fail("MemgraphStorage.db is required for Memgraph access", pytrace=False)
    if not hasattr(storage.db, "execute_and_fetch"):
        pytest.fail("MemgraphStorage.db.execute_and_fetch is missing", pytrace=False)
    try:
        result = next(storage.db.execute_and_fetch("RETURN 1 AS ok;"), None)
    except Exception as exc:  # pragma: no cover - connectivity/driver errors
        pytest.fail(f"Memgraph connection failed: {exc}", pytrace=False)
    if not result or result.get("ok") != 1:
        pytest.fail("Memgraph RETURN 1 check failed", pytrace=False)


@pytest.fixture()
def memgraph_storage():
    storage_cls = _get_memgraph_storage_class()
    host, port = _get_memgraph_connection_config()
    try:
        storage = storage_cls(host=host, port=port)
    except Exception as exc:  # pragma: no cover - fail-fast with clear reason
        pytest.fail(
            f"failed to create MemgraphStorage (check MEMGRAPH_HOST/MEMGRAPH_PORT): {exc}",
            pytrace=False,
        )

    _assert_memgraph_connection(storage)
    storage.db.execute("MATCH (n) DETACH DELETE n;")
    try:
        yield storage
    finally:
        storage.db.execute("MATCH (n) DETACH DELETE n;")
        if hasattr(storage, "close"):
            storage.close()

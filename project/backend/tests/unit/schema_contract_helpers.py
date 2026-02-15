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
        missing = exc.name
        if missing in {"gqlalchemy", "neo4j"}:
            pytest.fail(
                f"{module_path} requires {missing} but it is missing: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        message = str(exc)
        if "gqlalchemy" in message or "neo4j" in message:
            pytest.fail(
                f"{module_path} dependency import failed: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def get_schema_module():
    return _import_module("app.storage.schema")


def require_class(schema_module, name: str) -> type:
    if not hasattr(schema_module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    cls = getattr(schema_module, name)
    if not inspect.isclass(cls):
        pytest.fail(f"schema.{name} must be a class", pytrace=False)
    return cls


def require_relationship(schema_module, name: str) -> type:
    cls = require_class(schema_module, name)
    try:
        gqlalchemy = importlib.import_module("gqlalchemy")
    except ModuleNotFoundError as exc:
        pytest.fail(f"gqlalchemy is required: {exc}", pytrace=False)
    rel_base = getattr(gqlalchemy, "Relationship", None)
    if rel_base is None:
        pytest.fail("gqlalchemy.Relationship is missing", pytrace=False)
    if not issubclass(cls, rel_base):
        pytest.fail(
            f"schema.{name} must inherit gqlalchemy.Relationship", pytrace=False
        )
    return cls


def assert_explicit_label(cls: type) -> None:
    if "__label__" in cls.__dict__ or "__labels__" in cls.__dict__:
        return
    pytest.fail(
        f"schema.{cls.__name__} missing explicit label (__label__ or __labels__)",
        pytrace=False,
    )


def assert_fields_present(cls: type, required_fields: set[str]) -> None:
    annotations = getattr(cls, "__annotations__", {}) or {}
    missing = sorted(field for field in required_fields if field not in annotations)
    if missing:
        pytest.fail(
            f"schema.{cls.__name__} missing required fields: {missing}",
            pytrace=False,
        )


def build_instance(cls: type, **kwargs):
    try:
        return cls(**kwargs)
    except TypeError as exc:
        pytest.fail(
            f"failed to construct {cls.__name__} with {kwargs!r}: {exc}",
            pytrace=False,
        )


def assert_default_values(instance: object, expected: dict[str, object]) -> None:
    for name, expected_value in expected.items():
        actual = getattr(instance, name, None)
        assert actual == expected_value, (
            f"{instance.__class__.__name__}.{name} default mismatch: {actual!r}"
        )


def _module_index_metadata(schema_module) -> str | None:
    for attr in ("INDEX_DEFINITIONS", "INDEXES", "SCHEMA_INDEXES"):
        value = getattr(schema_module, attr, None)
        if value:
            return attr
    return None


def collect_index_definitions(schema_module) -> list[tuple[str, tuple[str, ...]]]:
    index_attr = _module_index_metadata(schema_module)
    if not index_attr:
        return []
    raw_indexes = getattr(schema_module, index_attr, None)
    if not raw_indexes:
        return []
    if isinstance(raw_indexes, dict):
        raw_indexes = [raw_indexes]
    indexes: list[tuple[str, tuple[str, ...]]] = []
    for entry in raw_indexes:
        if isinstance(entry, dict):
            label = entry.get("label")
            props = entry.get("properties", entry.get("property"))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            label = entry[0]
            props = entry[1]
        else:
            pytest.fail(
                f"unrecognized index definition entry: {entry!r}",
                pytrace=False,
            )
        if not label or not props:
            pytest.fail(
                f"index definition missing label/properties: {entry!r}",
                pytrace=False,
            )
        if isinstance(props, str):
            props_tuple = (props,)
        elif isinstance(props, (list, tuple, set)):
            props_tuple = tuple(props)
        else:
            pytest.fail(
                f"index properties must be string or list/tuple: {entry!r}",
                pytrace=False,
            )
        indexes.append((str(label), props_tuple))
    return indexes


def index_present(
    indexes: list[tuple[str, tuple[str, ...]]],
    label: str,
    props: tuple[str, ...],
) -> bool:
    for index_label, index_props in indexes:
        if index_label == label and (
            index_props == props or set(index_props) == set(props)
        ):
            return True
    return False

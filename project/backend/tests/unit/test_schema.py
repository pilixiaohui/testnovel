import importlib
import importlib.util
import inspect

import pytest

REQUIRED_MODEL_NAMES = [
    "Root",
    "Branch",
    "BranchHead",
    "Commit",
    "SceneOrigin",
    "SceneVersion",
    "Entity",
    "WorldSnapshot",
    "TemporalRelation",
]
NODE_MODEL_NAMES = [name for name in REQUIRED_MODEL_NAMES if name != "TemporalRelation"]
REQUIRED_FIELDS = {
    "Root": {"id", "logline", "theme", "ending", "created_at"},
    "Branch": {
        "id",
        "root_id",
        "branch_id",
        "parent_branch_id",
        "fork_scene_origin_id",
        "fork_commit_id",
    },
    "BranchHead": {"id", "root_id", "branch_id", "head_commit_id", "version"},
    "Commit": {"id", "parent_id", "message", "created_at", "root_id"},
    "SceneOrigin": {"id", "root_id", "title", "initial_commit_id", "sequence_index"},
    "SceneVersion": {
        "id",
        "scene_origin_id",
        "commit_id",
        "pov_character_id",
        "status",
        "expected_outcome",
        "conflict_type",
        "actual_outcome",
        "summary",
        "rendered_content",
        "logic_exception",
        "logic_exception_reason",
        "dirty",
    },
    "Entity": {"id", "entity_type", "semantic_states", "arc_status", "root_id", "branch_id"},
    "WorldSnapshot": {
        "id",
        "scene_version_id",
        "branch_id",
        "scene_seq",
        "entity_states",
    },
    "TemporalRelation": {
        "relation_type",
        "tension",
        "start_scene_seq",
        "end_scene_seq",
        "branch_id",
        "created_at",
        "invalidated_at",
    },
}
REQUIRED_INDEX_DEFINITIONS = [
    ("Root", ("id",)),
    ("Branch", ("id",)),
    ("Branch", ("root_id", "branch_id")),
    ("BranchHead", ("id",)),
    ("BranchHead", ("root_id", "branch_id")),
    ("Commit", ("id",)),
    ("Commit", ("root_id",)),
    ("SceneOrigin", ("id",)),
    ("SceneOrigin", ("root_id", "sequence_index")),
    ("SceneVersion", ("id",)),
    ("SceneVersion", ("scene_origin_id",)),
    ("SceneVersion", ("commit_id",)),
    ("Entity", ("id",)),
    ("Entity", ("root_id", "branch_id")),
    ("WorldSnapshot", ("id",)),
    ("WorldSnapshot", ("scene_version_id",)),
    ("WorldSnapshot", ("branch_id", "scene_seq")),
]
RELATIONSHIP_INDEX_DEFINITIONS = [
    ({"RELATION", "TemporalRelation"}, ("branch_id", "start_scene_seq")),
    ({"RELATION", "TemporalRelation"}, ("branch_id", "end_scene_seq")),
]


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


def test_schema_module_exists():
    _import_module("app.storage.schema")


def test_schema_models_exist():
    schema_module = _import_module("app.storage.schema")

    missing = [
        name for name in REQUIRED_MODEL_NAMES if not hasattr(schema_module, name)
    ]
    assert not missing, f"schema missing models: {missing}"

    not_classes = [
        name
        for name in REQUIRED_MODEL_NAMES
        if hasattr(schema_module, name)
        and not inspect.isclass(getattr(schema_module, name))
    ]
    assert not not_classes, f"schema models must be classes: {not_classes}"


def _has_explicit_label(cls: type) -> bool:
    return "__label__" in cls.__dict__ or "__labels__" in cls.__dict__


def _has_index_metadata(cls: type) -> bool:
    return "__indexes__" in cls.__dict__ or "__constraints__" in cls.__dict__


def _module_index_metadata(schema_module) -> str | None:
    for attr_name in ("INDEX_DEFINITIONS", "INDEXES", "SCHEMA_INDEXES"):
        value = getattr(schema_module, attr_name, None)
        if value:
            return attr_name
    return None


def _collect_index_definitions(schema_module) -> list[tuple[str, tuple[str, ...]]]:
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


def _props_match(actual: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    return actual == expected or set(actual) == set(expected)


def _index_present(
    indexes: list[tuple[str, tuple[str, ...]]],
    label: str,
    props: tuple[str, ...],
) -> bool:
    for index_label, index_props in indexes:
        if index_label == label and _props_match(index_props, props):
            return True
    return False


def _relationship_index_present(
    indexes: list[tuple[str, tuple[str, ...]]],
    labels: set[str],
    props: tuple[str, ...],
) -> bool:
    for index_label, index_props in indexes:
        if index_label in labels and _props_match(index_props, props):
            return True
    return False


def _relationship_type_name(cls: type) -> str:
    for attr in ("__type__", "__relationship_type__", "__label__"):
        value = getattr(cls, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return cls.__name__


def _is_establishes_state_relationship(cls: type) -> bool:
    rel_name = _relationship_type_name(cls).replace(" ", "").replace("_", "").upper()
    return rel_name in {"ESTABLISHESSTATE", "ESTABLISHES_STATE"}


def test_schema_labels_and_indexes_defined():
    schema_module = _import_module("app.storage.schema")
    model_classes = {name: getattr(schema_module, name) for name in REQUIRED_MODEL_NAMES}

    missing_labels = [
        name
        for name in NODE_MODEL_NAMES
        if not _has_explicit_label(model_classes[name])
    ]
    if missing_labels:
        pytest.fail(
            "schema missing explicit node labels; define __label__ or __labels__ on: "
            + ", ".join(missing_labels),
            pytrace=False,
        )

    index_source = _module_index_metadata(schema_module)
    indexed_models = [
        name
        for name, cls in model_classes.items()
        if _has_index_metadata(cls)
    ]
    if not index_source and not indexed_models:
        pytest.fail(
            "schema missing index definitions; expected module-level "
            "INDEX_DEFINITIONS/INDEXES/SCHEMA_INDEXES or class __indexes__/__constraints__",
            pytrace=False,
        )


def test_schema_phase1_field_contracts():
    schema_module = _import_module("app.storage.schema")

    missing_fields: dict[str, list[str]] = {}
    for name, required in REQUIRED_FIELDS.items():
        cls = getattr(schema_module, name, None)
        if cls is None:
            missing_fields[name] = sorted(required)
            continue
        annotations = getattr(cls, "__annotations__", {}) or {}
        missing = [field for field in required if field not in annotations]
        if missing:
            missing_fields[name] = sorted(missing)

    assert not missing_fields, f"schema missing required fields: {missing_fields}"


def test_schema_phase1_index_definitions_complete():
    schema_module = _import_module("app.storage.schema")
    indexes = _collect_index_definitions(schema_module)
    if not indexes:
        pytest.fail("schema missing module-level index definitions", pytrace=False)

    missing = [
        (label, props)
        for label, props in REQUIRED_INDEX_DEFINITIONS
        if not _index_present(indexes, label, props)
    ]
    missing_rel = [
        (labels, props)
        for labels, props in RELATIONSHIP_INDEX_DEFINITIONS
        if not _relationship_index_present(indexes, labels, props)
    ]

    if missing or missing_rel:
        pytest.fail(
            "schema missing required index definitions: "
            f"nodes={missing}, relationships={missing_rel}",
            pytrace=False,
        )


def test_schema_bridge_relationship_model_exists():
    schema_module = _import_module("app.storage.schema")
    try:
        gqlalchemy = importlib.import_module("gqlalchemy")
    except ModuleNotFoundError as exc:
        pytest.fail(f"gqlalchemy is required: {exc}", pytrace=False)
    rel_base = getattr(gqlalchemy, "Relationship", None)
    if rel_base is None:
        pytest.fail("gqlalchemy.Relationship is missing", pytrace=False)

    relationship_models = [
        cls
        for cls in schema_module.__dict__.values()
        if inspect.isclass(cls) and issubclass(cls, rel_base) and cls is not rel_base
    ]
    bridge_models = [
        cls for cls in relationship_models if _is_establishes_state_relationship(cls)
    ]
    if not bridge_models:
        pytest.fail(
            "schema missing bridge relationship model for ESTABLISHES_STATE",
            pytrace=False,
        )

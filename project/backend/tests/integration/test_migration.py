from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
MIGRATION_SCRIPT = SCRIPTS_DIR / "migrate_kuzu_to_memgraph.py"
ROLLBACK_SCRIPT = SCRIPTS_DIR / "rollback_migration.py"


def _load_script(path: Path, module_name: str):
    if not path.exists():
        pytest.fail(f"{path} is missing", pytrace=False)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"unable to load {path}", pytrace=False)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{path} missing dependency: {exc}", pytrace=False)
    except ImportError as exc:
        pytest.fail(f"{path} import failed: {exc}", pytrace=False)
    return module


def _get_migrator_class():
    module = _load_script(MIGRATION_SCRIPT, "migrate_kuzu_to_memgraph")
    if not hasattr(module, "KuzuToMemgraphMigrator"):
        pytest.fail("KuzuToMemgraphMigrator class is missing", pytrace=False)
    migrator_cls = module.KuzuToMemgraphMigrator
    if not inspect.isclass(migrator_cls):
        pytest.fail("KuzuToMemgraphMigrator must be a class", pytrace=False)
    return migrator_cls


def _get_rollback_function():
    module = _load_script(ROLLBACK_SCRIPT, "rollback_migration")
    if not hasattr(module, "rollback_migration"):
        pytest.fail("rollback_migration function is missing", pytrace=False)
    rollback_func = module.rollback_migration
    if not callable(rollback_func):
        pytest.fail("rollback_migration must be callable", pytrace=False)
    return rollback_func


class FakeKuzu:
    def __init__(self, nodes: list[dict], edges: list[dict]):
        self._nodes = [dict(node) for node in nodes]
        self._edges = [dict(edge) for edge in edges]

    def list_nodes(self) -> list[dict]:
        return [dict(node) for node in self._nodes]

    def list_edges(self) -> list[dict]:
        return [dict(edge) for edge in self._edges]


class FakeMemgraph:
    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, dict] = {}

    def insert_nodes(self, nodes: list[dict]) -> None:
        for node in nodes:
            self._nodes[node["id"]] = dict(node)

    def insert_edges(self, edges: list[dict]) -> None:
        for edge in edges:
            self._edges[edge["id"]] = dict(edge)

    def delete_nodes(self, node_ids: list[str]) -> None:
        for node_id in node_ids:
            del self._nodes[node_id]

    def delete_edges(self, edge_ids: list[str]) -> None:
        for edge_id in edge_ids:
            del self._edges[edge_id]

    def snapshot(self) -> dict[str, list[dict]]:
        return {
            "nodes": list(self._nodes.values()),
            "edges": list(self._edges.values()),
        }


def _build_sample_data() -> tuple[list[dict], list[dict]]:
    nodes = [
        {
            "id": "root-alpha",
            "label": "Root",
            "properties": {"logline": "seed", "theme": "fate"},
        },
        {
            "id": "scene-alpha",
            "label": "Scene",
            "properties": {"title": "Opening", "sequence_index": 1},
        },
        {
            "id": "entity-1",
            "label": "Entity",
            "properties": {"name": "Alice", "entity_type": "Character"},
        },
    ]
    edges = [
        {
            "id": "edge-1",
            "type": "HAS_SCENE",
            "from_id": "root-alpha",
            "to_id": "scene-alpha",
            "properties": {"sequence_index": 1},
        },
        {
            "id": "edge-2",
            "type": "HAS_ENTITY",
            "from_id": "scene-alpha",
            "to_id": "entity-1",
            "properties": {"role": "protagonist"},
        },
    ]
    return nodes, edges


def _build_bulk_data(node_count: int = 120) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    for index in range(1, node_count + 1):
        node_id = f"node-{index:03d}"
        nodes.append(
            {
                "id": node_id,
                "label": "Entity",
                "properties": {"index": index, "name": f"entity-{index:03d}"},
            }
        )
        if index > 1:
            edges.append(
                {
                    "id": f"edge-{index - 1:03d}",
                    "type": "LINKS_TO",
                    "from_id": f"node-{index - 1:03d}",
                    "to_id": node_id,
                    "properties": {"sequence_index": index - 1},
                }
            )
    return nodes, edges


def _map_by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items}


def _clone_snapshot(snapshot: dict[str, list[dict]]) -> dict[str, list[dict]]:
    nodes = [dict(node, properties=dict(node["properties"])) for node in snapshot["nodes"]]
    edges = [dict(edge, properties=dict(edge["properties"])) for edge in snapshot["edges"]]
    return {"nodes": nodes, "edges": edges}


def _snapshot_index(snapshot: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    return {
        "nodes": _map_by_id(snapshot["nodes"]),
        "edges": _map_by_id(snapshot["edges"]),
    }


def test_migration_script_contract():
    migrator_cls = _get_migrator_class()
    required_methods = ["export", "transform", "import_data", "validate_integrity"]
    for method_name in required_methods:
        if not hasattr(migrator_cls, method_name):
            pytest.fail(
                f"KuzuToMemgraphMigrator.{method_name} is missing",
                pytrace=False,
            )
        if not callable(getattr(migrator_cls, method_name)):
            pytest.fail(
                f"KuzuToMemgraphMigrator.{method_name} must be callable",
                pytrace=False,
            )


def test_migration_entrypoints_exist_in_code_root():
    assert MIGRATION_SCRIPT.exists()
    assert ROLLBACK_SCRIPT.exists()
    _load_script(MIGRATION_SCRIPT, "migrate_kuzu_to_memgraph_entry")
    _load_script(ROLLBACK_SCRIPT, "rollback_migration_entry")


def test_export_transform_import_flow_roundtrip():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    try:
        migrator = migrator_cls(source=source, target=target)
    except TypeError as exc:
        pytest.fail(
            f"KuzuToMemgraphMigrator must accept source/target for injection: {exc}",
            pytrace=False,
        )

    exported = migrator.export()
    if not isinstance(exported, dict):
        pytest.fail("export() must return a dict", pytrace=False)
    if "nodes" not in exported or "edges" not in exported:
        pytest.fail("export() must include nodes and edges", pytrace=False)
    assert len(exported["nodes"]) == len(nodes)
    assert len(exported["edges"]) == len(edges)

    transformed = migrator.transform(exported)
    if not isinstance(transformed, dict):
        pytest.fail("transform() must return a dict", pytrace=False)
    if "nodes" not in transformed or "edges" not in transformed:
        pytest.fail("transform() must include nodes and edges", pytrace=False)
    assert len(transformed["nodes"]) == len(nodes)
    assert len(transformed["edges"]) == len(edges)

    result = migrator.import_data(transformed)
    if not isinstance(result, dict):
        pytest.fail("import_data() must return a dict", pytrace=False)
    if "node_ids" not in result or "edge_ids" not in result:
        pytest.fail("import_data() must return node_ids and edge_ids", pytrace=False)

    snapshot = target.snapshot()
    assert len(snapshot["nodes"]) == len(nodes)
    assert len(snapshot["edges"]) == len(edges)
    node_map = _map_by_id(snapshot["nodes"])
    edge_map = _map_by_id(snapshot["edges"])
    assert node_map["root-alpha"]["properties"]["logline"] == "seed"
    assert edge_map["edge-1"]["properties"]["sequence_index"] == 1


def test_import_is_idempotent_for_same_payload():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)

    migrator.import_data(transformed)
    first_snapshot = _snapshot_index(target.snapshot())

    migrator.import_data(transformed)
    second_snapshot = _snapshot_index(target.snapshot())

    assert second_snapshot == first_snapshot


def test_validate_integrity_checks_counts_and_properties():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)
    migrator.import_data(transformed)
    snapshot = target.snapshot()

    migrator.validate_integrity(exported, snapshot, sample_size=len(nodes))

    broken = _clone_snapshot(snapshot)
    broken_index = _snapshot_index(broken)
    broken_index["nodes"]["root-alpha"]["properties"]["logline"] = "changed"
    broken["nodes"] = list(broken_index["nodes"].values())

    with pytest.raises(AssertionError):
        migrator.validate_integrity(exported, broken, sample_size=len(nodes))


def test_validate_integrity_respects_sample_size():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)
    migrator.import_data(transformed)
    snapshot = target.snapshot()

    broken = _clone_snapshot(snapshot)
    broken_index = _snapshot_index(broken)
    broken_index["nodes"]["root-alpha"]["properties"]["logline"] = "changed"
    broken["nodes"] = list(broken_index["nodes"].values())

    migrator.validate_integrity(exported, broken, sample_size=1)

    with pytest.raises(AssertionError):
        migrator.validate_integrity(exported, broken, sample_size=len(nodes))


def test_validate_integrity_supports_large_sample_validation():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_bulk_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)
    migrator.import_data(transformed)
    snapshot = target.snapshot()

    migrator.validate_integrity(exported, snapshot, sample_size=100)

    broken = _clone_snapshot(snapshot)
    broken_index = _snapshot_index(broken)
    broken_index["nodes"]["node-050"]["properties"]["index"] = 999
    broken["nodes"] = list(broken_index["nodes"].values())

    with pytest.raises(AssertionError):
        migrator.validate_integrity(exported, broken, sample_size=100)


def test_validate_integrity_detects_count_mismatch():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)
    migrator.import_data(transformed)
    snapshot = target.snapshot()

    broken = _clone_snapshot(snapshot)
    broken["nodes"] = broken["nodes"][:-1]

    with pytest.raises(AssertionError):
        migrator.validate_integrity(exported, broken, sample_size=1)


def test_imported_edges_reference_existing_nodes():
    migrator_cls = _get_migrator_class()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    exported = migrator.export()
    transformed = migrator.transform(exported)
    migrator.import_data(transformed)
    snapshot = target.snapshot()

    node_ids = {node["id"] for node in snapshot["nodes"]}
    for edge in snapshot["edges"]:
        assert edge["from_id"] in node_ids
        assert edge["to_id"] in node_ids


def test_rollback_reverts_imported_data_only():
    migrator_cls = _get_migrator_class()
    rollback = _get_rollback_function()
    nodes, edges = _build_sample_data()
    source = FakeKuzu(nodes, edges)
    target = FakeMemgraph()
    migrator = migrator_cls(source=source, target=target)

    target.insert_nodes(
        [
            {
                "id": "pre-root",
                "label": "Root",
                "properties": {"logline": "pre", "theme": "pre"},
            }
        ]
    )
    before = _snapshot_index(target.snapshot())

    exported = migrator.export()
    transformed = migrator.transform(exported)
    result = migrator.import_data(transformed)

    try:
        rollback(target=target, node_ids=result["node_ids"], edge_ids=result["edge_ids"])
    except TypeError as exc:
        pytest.fail(
            f"rollback_migration must accept target/node_ids/edge_ids: {exc}",
            pytrace=False,
        )

    after = _snapshot_index(target.snapshot())
    assert after == before

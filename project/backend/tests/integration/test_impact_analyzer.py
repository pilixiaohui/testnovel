import importlib
import importlib.util
import inspect
from uuid import uuid4

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


def _get_impact_analyzer_class():
    module = _import_module("app.services.impact_analyzer")
    if not hasattr(module, "ImpactAnalyzer"):
        pytest.fail("ImpactAnalyzer class is missing", pytrace=False)
    analyzer_cls = module.ImpactAnalyzer
    if not inspect.isclass(analyzer_cls):
        pytest.fail("ImpactAnalyzer must be a class", pytrace=False)
    return analyzer_cls


def _get_dependency_matrix_class():
    module = _import_module("app.services.dependency_matrix")
    if not hasattr(module, "DependencyMatrix"):
        pytest.fail("DependencyMatrix class is missing", pytrace=False)
    matrix_cls = module.DependencyMatrix
    if not inspect.isclass(matrix_cls):
        pytest.fail("DependencyMatrix must be a class", pytrace=False)
    return matrix_cls


class AsyncMemgraphAdapter:
    def __init__(self, db):
        self._db = db

    async def execute_and_fetch(self, query: str, params: dict | None = None):
        return list(self._db.execute_and_fetch(query, params or {}))


def _seed_scene_graph(db, *, root_id: str, branch_id: str, scene_ids: list[str]) -> None:
    db.execute(
        "CREATE (r:Root {id: $root_id, branch_id: $branch_id, logline: $logline, "
        "theme: $theme, ending: $ending})",
        {
            "root_id": root_id,
            "branch_id": branch_id,
            "logline": "seed",
            "theme": "seed",
            "ending": "seed",
        },
    )
    db.execute(
        "CREATE (s:Scene {id: $scene_id, scene_seq: $scene_seq, "
        "involved_entities: $entities})",
        {"scene_id": scene_ids[0], "scene_seq": 1, "entities": ["e1", "e2"]},
    )
    db.execute(
        "CREATE (s:Scene {id: $scene_id, scene_seq: $scene_seq, "
        "involved_entities: $entities})",
        {"scene_id": scene_ids[1], "scene_seq": 2, "entities": ["e2"]},
    )
    db.execute(
        "CREATE (s:Scene {id: $scene_id, scene_seq: $scene_seq, "
        "involved_entities: $entities})",
        {"scene_id": scene_ids[2], "scene_seq": 3, "entities": ["e3"]},
    )
    for scene_id in scene_ids:
        db.execute(
            "MATCH (r:Root {id: $root_id}), (s:Scene {id: $scene_id}) "
            "CREATE (r)-[:HAS_SCENE]->(s)",
            {"root_id": root_id, "scene_id": scene_id},
        )


@pytest.mark.asyncio
async def test_impact_analyzer_uses_scene_graph(memgraph_storage):
    analyzer_cls = _get_impact_analyzer_class()
    adapter = AsyncMemgraphAdapter(memgraph_storage.db)

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    scene_ids = [f"scene-{uuid4()}" for _ in range(3)]
    _seed_scene_graph(
        memgraph_storage.db, root_id=root_id, branch_id=branch_id, scene_ids=scene_ids
    )

    analyzer = analyzer_cls(adapter)
    state_changes = [
        {"entity_id": "e2", "state_key": "hp", "old": "100", "new": "25"}
    ]

    results = await analyzer.analyze_scene_impact(
        scene_id=scene_ids[0],
        branch_id=branch_id,
        state_changes=state_changes,
    )

    assert {item["scene_id"] for item in results} == {scene_ids[1]}
    assert results[0]["severity"] == "low"
    assert "e2" in results[0]["reason"]


def test_dependency_matrix_builds_from_memgraph_scene_entities(memgraph_storage):
    matrix_cls = _get_dependency_matrix_class()

    root_id = f"root-{uuid4()}"
    branch_id = "main"
    scene_ids = [f"scene-{uuid4()}" for _ in range(3)]
    _seed_scene_graph(
        memgraph_storage.db, root_id=root_id, branch_id=branch_id, scene_ids=scene_ids
    )

    rows = list(
        memgraph_storage.db.execute_and_fetch(
            "MATCH (r:Root {id: $root_id})-[:HAS_SCENE]->(s:Scene) "
            "RETURN s.id AS scene_id, s.involved_entities AS involved_entities",
            {"root_id": root_id},
        )
    )
    scene_entities = {row["scene_id"]: row["involved_entities"] for row in rows}
    matrix = matrix_cls.from_scene_entities(scene_entities)

    impacted = matrix.get_impacted_scenes(["e2"])

    assert set(impacted) == {scene_ids[0], scene_ids[1]}

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
    except ImportError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_dependency_matrix_class():
    module = _import_module("app.services.dependency_matrix")
    if not hasattr(module, "DependencyMatrix"):
        pytest.fail("DependencyMatrix class is missing", pytrace=False)
    matrix_cls = module.DependencyMatrix
    if not inspect.isclass(matrix_cls):
        pytest.fail("DependencyMatrix must be a class", pytrace=False)
    return matrix_cls


def _get_dependency_matrix_cache_class():
    module = _import_module("app.services.dependency_matrix")
    if not hasattr(module, "DependencyMatrixCache"):
        pytest.fail("DependencyMatrixCache class is missing", pytrace=False)
    cache_cls = module.DependencyMatrixCache
    if not inspect.isclass(cache_cls):
        pytest.fail("DependencyMatrixCache must be a class", pytrace=False)
    return cache_cls


def test_dependency_matrix_module_exists():
    _import_module("app.services.dependency_matrix")


def test_dependency_matrix_has_required_methods():
    matrix_cls = _get_dependency_matrix_class()
    if not hasattr(matrix_cls, "from_scene_entities"):
        pytest.fail("DependencyMatrix.from_scene_entities is missing", pytrace=False)
    if not hasattr(matrix_cls, "get_impacted_scenes"):
        pytest.fail("DependencyMatrix.get_impacted_scenes is missing", pytrace=False)


def test_dependency_matrix_build_and_query_consistency():
    matrix_cls = _get_dependency_matrix_class()

    scene_entities = {
        "scene-alpha": ["e1", "e2"],
        "scene-2": ["e2"],
        "scene-3": ["e3"],
    }

    matrix = matrix_cls.from_scene_entities(scene_entities)

    impacted = matrix.get_impacted_scenes(["e2"])
    assert set(impacted) == {"scene-alpha", "scene-2"}

    impacted_multi = matrix.get_impacted_scenes(["e1", "e3"])
    assert set(impacted_multi) == {"scene-alpha", "scene-3"}


def test_dependency_matrix_query_uses_entity_ids_only():
    matrix_cls = _get_dependency_matrix_class()

    class CountingDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.getitem_calls = 0

        def __getitem__(self, key):
            self.getitem_calls += 1
            return super().__getitem__(key)

    entity_to_scenes = CountingDict(
        {
            "e1": {"scene-alpha"},
            "e2": {"scene-2"},
            "e3": {"scene-3"},
            "e4": {"scene-4"},
        }
    )

    matrix = matrix_cls(entity_to_scenes)

    impacted = matrix.get_impacted_scenes(["e1", "e3"])

    assert set(impacted) == {"scene-alpha", "scene-3"}
    assert entity_to_scenes.getitem_calls == 2


def test_dependency_matrix_accuracy_metrics():
    matrix_cls = _get_dependency_matrix_class()

    scene_entities = {
        "scene-alpha": ["e1", "e2"],
        "scene-2": ["e2"],
        "scene-3": ["e3"],
        "scene-4": [],
    }

    matrix = matrix_cls.from_scene_entities(scene_entities)
    predicted = set(matrix.get_impacted_scenes(["e2"]))
    expected = {"scene-alpha", "scene-2"}

    assert predicted, "expected impacted scenes for accuracy check"

    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted)
    recall = true_positive / len(expected)

    assert precision >= 0.85
    assert recall >= 0.85


def test_dependency_matrix_cache_reuses_matrix_per_root_branch():
    cache_cls = _get_dependency_matrix_cache_class()
    matrix_cls = _get_dependency_matrix_class()

    calls = {"count": 0}

    def builder():
        calls["count"] += 1
        return matrix_cls.from_scene_entities({"scene-alpha": ["e1"]})

    cache = cache_cls()
    first = cache.get_or_build(root_id="root-alpha", branch_id="main", builder=builder)
    second = cache.get_or_build(root_id="root-alpha", branch_id="main", builder=builder)

    assert first is second
    assert calls["count"] == 1


def test_dependency_matrix_cache_invalidate_triggers_rebuild():
    cache_cls = _get_dependency_matrix_cache_class()
    matrix_cls = _get_dependency_matrix_class()

    calls = {"count": 0}

    def builder():
        calls["count"] += 1
        return matrix_cls.from_scene_entities({"scene-alpha": ["e1"]})

    cache = cache_cls()
    first = cache.get_or_build(root_id="root-alpha", branch_id="main", builder=builder)
    cache.invalidate(root_id="root-alpha", branch_id="main")
    second = cache.get_or_build(root_id="root-alpha", branch_id="main", builder=builder)

    assert first is not second
    assert calls["count"] == 2

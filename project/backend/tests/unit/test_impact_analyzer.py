import asyncio
import importlib
import importlib.util
import inspect
import math
import time
from unittest.mock import AsyncMock, Mock

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


def _get_dependency_matrix_cache_class():
    module = _import_module("app.services.dependency_matrix")
    if not hasattr(module, "DependencyMatrixCache"):
        pytest.fail("DependencyMatrixCache class is missing", pytrace=False)
    cache_cls = module.DependencyMatrixCache
    if not inspect.isclass(cache_cls):
        pytest.fail("DependencyMatrixCache must be a class", pytrace=False)
    return cache_cls


def _build_analyzer_with_cache(analyzer_cls, db, cache):
    try:
        return analyzer_cls(db, dependency_matrix_cache=cache)
    except TypeError:
        pytest.fail("ImpactAnalyzer must accept dependency_matrix_cache", pytrace=False)


def test_impact_analyzer_module_exists():
    _import_module("app.services.impact_analyzer")


def test_impact_analyzer_has_analyze_scene_impact():
    analyzer_cls = _get_impact_analyzer_class()
    if not hasattr(analyzer_cls, "analyze_scene_impact"):
        pytest.fail("ImpactAnalyzer.analyze_scene_impact is missing", pytrace=False)
    method = getattr(analyzer_cls, "analyze_scene_impact")
    if not callable(method):
        pytest.fail("ImpactAnalyzer.analyze_scene_impact must be callable", pytrace=False)
    assert inspect.iscoroutinefunction(method), "ImpactAnalyzer.analyze_scene_impact must be async"


@pytest.mark.asyncio
async def test_analyze_scene_impact_returns_severity_and_reason():
    analyzer_cls = _get_impact_analyzer_class()
    db = Mock()
    db.execute_and_fetch = AsyncMock(
        return_value=[
            {
                "scene_origin_id": "scene-6",
                "scene_id": "scene-6",
                "scene_seq": 6,
                "involved_entities": ["john"],
            }
        ]
    )
    analyzer = analyzer_cls(db)

    if hasattr(analyzer, "_get_scene_sequence"):
        analyzer._get_scene_sequence = AsyncMock(return_value=5)
    if hasattr(analyzer, "_get_root_id"):
        analyzer._get_root_id = AsyncMock(return_value="root-alpha")

    state_changes = [
        {"entity_id": "john", "state_key": "hp", "old": "100%", "new": "10%"}
    ]

    results = await analyzer.analyze_scene_impact(
        scene_id="scene-5",
        branch_id="main",
        state_changes=state_changes,
    )

    assert isinstance(results, list)
    assert results, "expected at least one impacted scene"
    first = results[0]
    assert "scene_id" in first
    assert "severity" in first
    assert "reason" in first
    assert first["scene_id"] == "scene-6"
    assert first["severity"] in {"high", "medium", "low"}
    assert isinstance(first["reason"], str)
    assert first["reason"]


@pytest.mark.asyncio
async def test_analyze_scene_impact_builds_query_from_state_changes():
    analyzer_cls = _get_impact_analyzer_class()
    db = Mock()
    db.execute_and_fetch = AsyncMock(
        return_value=[
            {
                "scene_id": "scene-8",
                "scene_seq": 8,
                "involved_entities": ["e1", "e2"],
            }
        ]
    )
    analyzer = analyzer_cls(db)
    analyzer._get_root_id = AsyncMock(return_value="root-alpha")
    analyzer._get_scene_sequence = AsyncMock(return_value=6)

    state_changes = [
        {"entity_id": "e1", "state_key": "hp", "old": "90%", "new": "50%"},
        {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
    ]

    results = await analyzer.analyze_scene_impact(
        scene_id="scene-6",
        branch_id="main",
        state_changes=state_changes,
    )

    assert db.execute_and_fetch.call_count == 1
    call_args = db.execute_and_fetch.call_args
    query, params = call_args.args
    assert "MATCH (r:Root" in query
    assert params["root_id"] == "root-alpha"
    assert params["scene_seq"] == 6
    assert params["entity_ids"] == ["e1", "e2"]
    assert results[0]["severity"] == "medium"
    assert "e1" in results[0]["reason"]
    assert "e2" in results[0]["reason"]


def test_analyze_scene_impact_severity_reasonability_threshold():
    analyzer_cls = _get_impact_analyzer_class()
    analyzer = analyzer_cls(Mock())

    cases = [
        ([{"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"}], "low"),
        ([{"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"}], "low"),
        ([{"entity_id": "e3", "state_key": "loc", "old": "home", "new": "road"}], "low"),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
            ],
            "medium",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
            ],
            "medium",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
            ],
            "medium",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
                {"entity_id": "e3", "state_key": "loc", "old": "home", "new": "road"},
            ],
            "high",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
                {"entity_id": "e3", "state_key": "loc", "old": "home", "new": "road"},
            ],
            "high",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
                {"entity_id": "e3", "state_key": "loc", "old": "home", "new": "road"},
                {"entity_id": "e4", "state_key": "status", "old": "ok", "new": "down"},
            ],
            "high",
        ),
        (
            [
                {"entity_id": "e1", "state_key": "hp", "old": "100", "new": "90"},
                {"entity_id": "e2", "state_key": "mood", "old": "calm", "new": "angry"},
                {"entity_id": "e3", "state_key": "loc", "old": "home", "new": "road"},
            ],
            "high",
        ),
    ]

    matched = 0
    for state_changes, expected in cases:
        if analyzer._calculate_severity(state_changes) == expected:
            matched += 1

    severity_accuracy = matched / len(cases)
    assert severity_accuracy >= 0.90


@pytest.mark.asyncio
async def test_analyze_scene_impact_accuracy_precision_recall_thresholds():
    analyzer_cls = _get_impact_analyzer_class()
    db = Mock()
    db.execute_and_fetch = AsyncMock(
        return_value=[
            {"scene_id": "scene-2", "scene_seq": 2},
            {"scene_id": "scene-3", "scene_seq": 3},
            {"scene_id": "scene-5", "scene_seq": 5},
        ]
    )
    analyzer = analyzer_cls(db)
    analyzer._get_root_id = AsyncMock(return_value="root-alpha")
    analyzer._get_scene_sequence = AsyncMock(return_value=1)

    state_changes = [
        {"entity_id": "e2", "state_key": "hp", "old": "90", "new": "50"}
    ]

    results = await analyzer.analyze_scene_impact(
        scene_id="scene-alpha",
        branch_id="main",
        state_changes=state_changes,
    )

    predicted = {item["scene_id"] for item in results}
    expected = {"scene-2", "scene-3", "scene-5"}
    all_scenes = {
        "scene-2",
        "scene-3",
        "scene-4",
        "scene-5",
        "scene-6",
        "scene-7",
        "scene-8",
        "scene-9",
        "scene-ten",
        "scene-eleven",
    }

    assert predicted
    assert expected
    assert predicted.issubset(all_scenes)
    assert expected.issubset(all_scenes)

    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    true_negative = len(all_scenes - predicted - expected)

    accuracy = (true_positive + true_negative) / len(all_scenes)
    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)

    assert accuracy >= 0.85
    assert precision >= 0.85
    assert recall >= 0.85


@pytest.mark.asyncio
async def test_analyze_scene_impact_uses_dependency_matrix_cache(monkeypatch):
    analyzer_cls = _get_impact_analyzer_class()
    _get_dependency_matrix_cache_class()

    db = Mock()
    db.execute_and_fetch = AsyncMock(return_value=[])

    class StubMatrix:
        def __init__(self):
            self.calls: list[tuple[str, ...]] = []

        def get_impacted_scenes(self, entity_ids):
            self.calls.append(tuple(entity_ids))
            return ["scene-7", "scene-8"]

    class FakeCache:
        def __init__(self, matrix):
            self.matrix = matrix
            self.calls: list[tuple[str, str]] = []

        def get_or_build(self, *, root_id, branch_id, builder):
            if not callable(builder):
                pytest.fail(
                    "DependencyMatrixCache.get_or_build must receive builder",
                    pytrace=False,
                )
            self.calls.append((root_id, branch_id))
            return self.matrix

    matrix = StubMatrix()
    cache = FakeCache(matrix)
    analyzer = _build_analyzer_with_cache(analyzer_cls, db, cache)

    analyzer._get_root_id = AsyncMock(return_value="root-alpha")
    analyzer._get_scene_sequence = AsyncMock(return_value=4)
    monkeypatch.setattr(analyzer, "_calculate_severity", lambda changes: "high")
    monkeypatch.setattr(
        analyzer, "_build_reason", lambda scene_id, changes: f"reason-{scene_id}"
    )

    state_changes = [
        {"entity_id": "e2", "state_key": "hp", "old": "90", "new": "50"}
    ]

    results = await analyzer.analyze_scene_impact(
        scene_id="scene-4",
        branch_id="main",
        state_changes=state_changes,
    )

    assert cache.calls == [("root-alpha", "main")]
    assert matrix.calls == [("e2",)]
    assert [item["scene_id"] for item in results] == ["scene-7", "scene-8"]
    assert [item["severity"] for item in results] == ["high", "high"]
    assert results[0]["reason"] == "reason-scene-7"


@pytest.mark.asyncio
async def test_analyze_scene_impact_latency_under_threshold():
    analyzer_cls = _get_impact_analyzer_class()

    class SlowDB:
        def __init__(self):
            self.call_count = 0

        async def execute_and_fetch(self, query, params):
            self.call_count += 1
            await asyncio.sleep(0.01)
            if "RETURN r.id AS root_id" in query:
                return [{"root_id": "root-alpha"}]
            if "RETURN s.scene_seq AS scene_seq LIMIT 1" in query:
                return [{"scene_seq": 1}]
            return [
                {
                    "scene_id": "scene-2",
                    "scene_seq": 2,
                    "involved_entities": ["e1"],
                }
            ]

    db = SlowDB()
    analyzer = analyzer_cls(db)
    state_changes = [
        {"entity_id": "e1", "state_key": "hp", "old": "100%", "new": "80%"}
    ]

    samples = []
    for _ in range(20):
        start = time.monotonic()
        results = await analyzer.analyze_scene_impact(
            scene_id="scene-alpha",
            branch_id="main",
            state_changes=state_changes,
        )
        samples.append(time.monotonic() - start)
        assert results

    assert db.call_count == 60
    samples.sort()
    index = math.ceil(0.95 * len(samples)) - 1
    p95 = samples[index]
    assert p95 < 0.1

import importlib.util
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

WRITE_P95_MS_MAX = 2000.0
WRITE_P99_MS_MAX = 4000.0
WRITE_QPS_MIN = 0.5
READ_P95_MS_MAX = 2000.0
READ_P99_MS_MAX = 4000.0
READ_QPS_MIN = 0.5


def _load_benchmark_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "performance_benchmark.py"
    if not module_path.exists():
        pytest.fail("scripts/performance_benchmark.py is missing", pytrace=False)
    spec = importlib.util.spec_from_file_location("performance_benchmark", module_path)
    if spec is None or spec.loader is None:
        pytest.fail("failed to load performance_benchmark module", pytrace=False)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        pytest.fail(f"{name} is required for benchmark tests", pytrace=False)
    return value


def _assert_memgraph_ready(storage) -> None:
    result = next(storage.db.execute_and_fetch("RETURN 1 AS ok;"), None)
    if not result or result.get("ok") != 1:
        pytest.fail("Memgraph RETURN 1 check failed", pytrace=False)


def test_benchmark_metrics_smoke():
    _require_env("MEMGRAPH_HOST")
    _require_env("MEMGRAPH_PORT")

    benchmark = _load_benchmark_module()
    root_id = f"bench-test-{uuid4()}"
    branch_id = f"bench-test-{uuid4()}"

    storage = benchmark._create_storage()
    try:
        _assert_memgraph_ready(storage)
        _, scene_ids = benchmark._seed_graph(
            storage,
            root_id=root_id,
            branch_id=branch_id,
            entity_count=2,
            scene_count=2,
            relation_count=1,
        )
    finally:
        storage.close()

    write_metrics = benchmark._benchmark_writes(
        root_id=root_id,
        branch_id=branch_id,
        total_ops=5,
        concurrency=1,
        seed=1,
    )
    read_metrics = benchmark._benchmark_reads(
        scene_ids=scene_ids,
        branch_id=branch_id,
        total_ops=5,
        concurrency=1,
        seed=1,
    )

    benchmark._print_metrics("Write benchmark (test)", write_metrics)
    benchmark._print_metrics("Read benchmark (test)", read_metrics)
    print(
        "benchmark_summary "
        f"write_qps={write_metrics.qps:.2f} write_p99_ms={write_metrics.p99_ms:.2f} "
        f"read_qps={read_metrics.qps:.2f} read_p99_ms={read_metrics.p99_ms:.2f}"
    )

    assert write_metrics.count == 5
    assert read_metrics.count == 5
    assert write_metrics.p99_ms >= 0
    assert read_metrics.p99_ms >= 0
    assert write_metrics.p95_ms <= WRITE_P95_MS_MAX
    assert write_metrics.p99_ms <= WRITE_P99_MS_MAX
    assert write_metrics.qps >= WRITE_QPS_MIN
    assert read_metrics.p95_ms <= READ_P95_MS_MAX
    assert read_metrics.p99_ms <= READ_P99_MS_MAX
    assert read_metrics.qps >= READ_QPS_MIN

    storage = benchmark._create_storage()
    try:
        benchmark._cleanup(storage, root_id=root_id)
    finally:
        storage.close()
